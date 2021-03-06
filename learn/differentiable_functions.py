import jax.numpy as jnp


class FunctionWithDerivative:
    def __init__(self, f, df, extra_args=None):
        self.f = f
        self.df = df


def sigmoid(x):
    return 1 / (1 + jnp.exp(-x))


def d_sigmoid(x):
    return jnp.diag(jnp.exp(-x) / ((1 + jnp.exp(-x)) ** 2))


sigmoid_fd = FunctionWithDerivative(sigmoid, d_sigmoid)


def relu(x):
    return jnp.maximum(x, 0.0)


def d_relu(x):
    return jnp.diag(jnp.where(x > 0, 1.0, 0.0))


relu_fd = FunctionWithDerivative(relu, d_relu)


def tanh(x, scale=1.0):
    return scale * jnp.tanh(x)


def d_tanh(x, scale=1.0):
    return jnp.diag(scale / (jnp.cosh(x) ** 2))


tanh_fd = FunctionWithDerivative(tanh, d_tanh)


def square_diff(y0, y):
    return jnp.dot(y0 - y, y0 - y)


def d_square_diff(y0, y):
    return -2 * (y0 - y)


square_diff_fd = FunctionWithDerivative(square_diff, d_square_diff)


def softmax(x):
    exp = jnp.exp(x)
    return exp / jnp.sum(exp)


def d_softmax(x):
    exp = jnp.exp(x)
    denum = jnp.sum(exp)
    diag = jnp.diag(exp / denum)

    off_diag = jnp.array(jnp.matrix([
        jnp.array([-(exp[i] * exp[j]) / denum ** 2
                   for j in range(len(x))
                   ]) for i in range(len(x))
    ]))
    return diag + off_diag


softmax_fd = FunctionWithDerivative(softmax, d_softmax)


def softmax_i(x, i):
    exp = jnp.exp(x)
    return exp[i] / jnp.sum(exp)


def d_softmax_i(x, i):
    exp = jnp.exp(x)
    return -(exp[i] / jnp.sum(exp)) ** 2


softmax_i_fd = FunctionWithDerivative(softmax_i, d_softmax_i)


def log(x, ind):
    return jnp.log(x)


def d_log(x):
    return 1 / x


log_fd = FunctionWithDerivative(log, d_log)


def log_policy(ind, x):
    return jnp.log(x[ind])


def d_log_policy(ind, x):
    return jnp.array([min(1 / x[i], 1000) if i == ind else 0 for i in range(len(x))])


log_policy_fd = FunctionWithDerivative(log_policy, d_log_policy)


def cross_entropy(p, p0):
    print(p, p0)
    return -jnp.dot(p0, jnp.log(p))


def d_cross_entropy(p, p0):
    print(p, p0, -jnp.dot(p0, 1 / p))
    return -jnp.dot(p0, 1 / p)


def cross_entropy_1d(p, p0):
    return -p0 * jnp.log(p) - (1 - p0) * jnp.log(1 - p)


def d_cross_entropy_1d(p, p0):
    return -p0 / p + (1 - p0) / (1 - p)


cross_entropy_fd = FunctionWithDerivative(cross_entropy, d_cross_entropy)

cross_entropy_1d_fd = FunctionWithDerivative(cross_entropy_1d, d_cross_entropy_1d)


def linear(x):
    return x


def d_linear(x):
    return 1


linear_fd = FunctionWithDerivative(linear, d_linear)


def huber(y0, y):
    sq = jnp.dot(y0 - y, y0 - y)
    if sq < 1:
        return sq / 2
    else:
        return jnp.sqrt(sq) - 0.5


def d_huber(y0, y):
    sq = jnp.dot(y0 - y, y0 - y)

    if sq < 1:
        return -(y0 - y)
    else:
        return -(y0 - y) / jnp.linalg.norm(y0 - y)


huber_fd = FunctionWithDerivative(huber, d_huber)

string_to_differentiable_function = {
    'sigmoid': sigmoid_fd,
    'relu': relu_fd,
    'tanh': tanh_fd,
    'square_diff': square_diff_fd,
    'softmax': softmax_fd,
    'huber': huber_fd,
    'log': log_fd,
    'log_policy': log_policy_fd,
    'cross_entropy': cross_entropy_fd,
    'cross_entropy_1d': cross_entropy_1d_fd,
    'linear': linear_fd,
    'none': None
}


def get_function(function_string):
    return string_to_differentiable_function[function_string].f


def get_derivative(function_string):
    return string_to_differentiable_function[function_string].df
