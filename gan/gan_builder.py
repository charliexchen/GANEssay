import copy
import numpy as np
import os
import sys
import tensorflow.keras.backend as kb
import yaml
from keras import Sequential
from keras import backend as K
from keras.constraints import Constraint
from keras.layers import Dense, Activation, LeakyReLU, InputLayer
from keras.optimizers import Adam

from learn.net import DenseNet


def wasserstein_loss(y_actual, y_pred):
    loss = y_actual * y_pred / y_actual.shape[0]

    return loss


class GANBuilder:
    def __init__(self, config_path=None, config=None):
        if config is None:
            if config_path is None:
                raise IOError("No config file specified")
            config = self._get_config(config_path)
        self.model_config = config['model_config']
        self.dashboard_config = config['dashboard_config']
        self.generator, self.discriminator, self.adversarial = self._compile_models()
        self.generation = 0

    @staticmethod
    def _get_config(config_path):
        with open(config_path) as f:
            return yaml.load(f, Loader=yaml.FullLoader)

    def _generate_data_real(self, batch_size):
        data_config = self.model_config['target_distribution']
        if data_config['name'] == 'normal':
            return np.random.normal(loc=data_config['mean'], scale=data_config['standard_deviation'],
                                    size=[batch_size, 1])
        if data_config['name'] == 'bimodal':
            half_batch_size = int(batch_size / 2)
            data = np.concatenate(
                (np.random.normal(loc=data_config['mean_one'], scale=data_config['standard_deviation'],
                                  size=[half_batch_size, 1]),
                 np.random.normal(loc=data_config['mean_two'], scale=data_config['standard_deviation'],
                                  size=[half_batch_size, 1]))
            )
            np.random.shuffle(data)
            return data
        else:
            raise LookupError("Invalid data generation type in config")

    def _generate_noise(self, batch_size):
        noise_config = self.model_config['generator_config']
        if noise_config['noise_type'] == 'normal':
            noise = np.random.uniform(low=-1.0, high=1.0, size=(batch_size, noise_config['noise_dim']))
        elif noise_config['noise_type'] == 'uniform':
            noise = np.random.normal(loc=0, scale=1.0, size=(batch_size, noise_config['noise_dim']))
        else:
            LookupError("Invalid noise type in config")
        return noise

    def generate_samples(self, batch_size):
        noise = self._generate_noise(batch_size)
        return self.generator.predict(noise)

    def _train_discriminator_batch(self):
        batch_size = self.model_config['discriminator_config']['batch_size']
        split_size = int(batch_size / 2)
        real_data = self._generate_data_real(split_size)
        fake_data = self.generate_samples(split_size)
        labels = np.concatenate((np.ones(split_size), -np.ones(split_size)))
        shuffling = np.random.permutation(len(labels))

        labels_shuffled = labels[shuffling]
        data_shuffled = np.concatenate((real_data, fake_data))[shuffling]

        error = self.discriminator.train_on_batch(data_shuffled, labels_shuffled)
        if self.model_config['gan_type'] == 'wasserstein':
            clipping = self.model_config['gan_params']['clipping']
            for layer in self.discriminator.layers:
                new_weights = []
                for weights in layer.get_weights():
                    new_weights.append(K.clip(weights, -clipping, clipping))
                layer.set_weights(new_weights)
        return fake_data, error

    def _train_generator_batch(self):
        batch_size = self.model_config['generator_config']['batch_size']
        noise = self._generate_noise(batch_size)
        labels = np.ones([batch_size, 1])
        self.adversarial.train_on_batch(noise, labels)

    def _train_generator_batch_unrolled(self, k=5):
        batch_size = self.model_config['generator_config']['batch_size']
        noise = self._generate_noise(batch_size)
        labels = np.ones([batch_size, 1])
        discriminator_weights = self.discriminator.get_weights()
        for _ in range(k):
            self._train_discriminator_batch()
        self.adversarial.train_on_batch(noise, labels)
        self.discriminator.set_weights(discriminator_weights)

    @staticmethod
    def _build_model(params):
        model = Sequential()
        model.add(InputLayer(input_shape=params['input_shape']))
        for layer_config in params['layers']:
            if layer_config['type'] == 'dense':
                model.add(Dense(layer_config['units']))
            elif layer_config['type'] == 'leaky_relu':
                model.add(LeakyReLU(layer_config['alpha']))
            elif layer_config['type'] == 'sigmoid':
                model.add(Activation('sigmoid'))
            else:
                raise ValueError('No corresponding layer config for {}'.format(layer_config['type']))
        model.summary()
        return model

    def _build_generator(self):
        generator_config = copy.deepcopy(self.model_config['generator_config'])
        generator_config['input_shape'] = (generator_config['noise_dim'],)
        return GANBuilder._build_model(generator_config)

    def _build_discriminator(self):
        discriminator_config = copy.deepcopy(self.model_config['discriminator_config'])
        # input size of the discriminator should be the same as the generator's output
        generator_layers = self.model_config['generator_config']['layers']
        discriminator_config['input_shape'] = (generator_layers[-1]['units'],)
        return GANBuilder._build_model(discriminator_config)

    @staticmethod
    def _build_optimiser(optimiser_config):
        if optimiser_config['type'] == 'adam':
            return Adam(lr=optimiser_config['learning_rate'])
        else:
            raise ValueError('No corresponding optimiser config for {}'.format(optimiser_config['type']))

    def _compile_models(self):
        discriminator = self._build_discriminator()
        discriminator_optimiser_config = self.model_config['discriminator_config']['optimiser']
        discriminator_optimiser = GANBuilder._build_optimiser(discriminator_optimiser_config)
        if self.model_config['gan_type'] == 'standard':
            loss = 'binary_crossentropy'
        elif self.model_config['gan_type'] == 'wasserstein':
            loss = wasserstein_loss
        discriminator.compile(loss=loss, optimizer=discriminator_optimiser)

        generator = self._build_generator()
        generator_optimiser_config = self.model_config['generator_config']['optimiser']
        generator_optimiser = GANBuilder._build_optimiser(generator_optimiser_config)

        adversarial = Sequential()
        adversarial.add(generator)
        adversarial.add(discriminator)
        adversarial.layers[1].trainable = False
        adversarial.compile(loss=loss, optimizer=generator_optimiser)

        return generator, discriminator, adversarial

    def train_one_batch(self):
        self._train_generator_batch()
        if 'iterations' in self.model_config['discriminator_config']:
            k = self.model_config['discriminator_config']['iterations']
        else:
            k = 1
        for _ in range(k):
            samples, error = self._train_discriminator_batch()
        return samples

    def train_equilibrium_gan(self, temperature = 0.01):
        def reject(generation):
            random_number = np.random.random_sample()
            rejection_probability = 1-np.exp(-temperature * generation)
            return rejection_probability<random_number
        self.generation+=1
        samples, error = self._train_discriminator_batch()
        backup_weights = self.discriminator.get_weights(),  self.generator.get_weights()
        self._train_generator_batch()
        for _ in range(10):
            _samples, proposal_error = self._train_discriminator_batch()

        if proposal_error>error or reject(self.generation):
            error = proposal_error
        else:
            self.discriminator.set_weights(backup_weights[0])
            self.generator.set_weights(backup_weights[1])



if __name__ == "__main__":
    gan = GANBuilder('gan_config.yaml')
    for _ in range(1):
        gan.train_one_batch()
    print('finished')
