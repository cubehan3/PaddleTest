import numpy as np
import paddle


class LayerCase(paddle.nn.Layer):
    """
    case名称: atan2_base
    api简介: 对x/y进行逐元素的arctangent运算，通过符号确定象限
    """

    def __init__(self):
        super(LayerCase, self).__init__()

    def forward(self, x, y, ):
        """
        forward
        """
        out = paddle.atan2(x, y,  )
        return out


def create_tensor_inputs():
    """
    paddle tensor
    """
    inputs = (paddle.to_tensor(-5 + (5 - -5) * np.random.random([6, 6]).astype('float32'), dtype='float32', stop_gradient=False), paddle.to_tensor(-5 + (5 - -5) * np.random.random([6, 6]).astype('float32'), dtype='float32', stop_gradient=False), )
    return inputs


def create_numpy_inputs():
    """
    numpy array
    """
    inputs = (-5 + (5 - -5) * np.random.random([6, 6]).astype('float32'), -5 + (5 - -5) * np.random.random([6, 6]).astype('float32'), )
    return inputs
