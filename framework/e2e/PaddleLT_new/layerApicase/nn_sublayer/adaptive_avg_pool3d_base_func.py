import numpy as np
import paddle


class LayerCase(paddle.nn.Layer):
    """
    case名称: adaptive_avg_pool3d_base
    api简介: 3维自适应平均池化
    """

    def __init__(self):
        super(LayerCase, self).__init__()

    def forward(self, x, ):
        """
        forward
        """
        out = paddle.nn.functional.adaptive_avg_pool3d(x,  output_size=[3, 3, 3], )
        return out


def create_tensor_inputs():
    """
    paddle tensor
    """
    inputs = (paddle.to_tensor(-1 + (1 - -1) * np.random.random([2, 3, 8, 32, 32]).astype('float32'), dtype='float32', stop_gradient=False), )
    return inputs


def create_numpy_inputs():
    """
    numpy array
    """
    inputs = (-1 + (1 - -1) * np.random.random([2, 3, 8, 32, 32]).astype('float32'), )
    return inputs
