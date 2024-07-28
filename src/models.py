import logging

import keras.backend as K
import math
from keras import layers
from keras import regularizers
from keras.layers import Input, GRU
from keras.layers.convolutional import Conv2D
from keras.layers.core import Lambda, Dense, RepeatVector
from keras.layers.core import Reshape
from keras.layers import BatchNormalization
from keras.models import Model
from tensorflow.keras.utils import plot_model
import tensorflow as tf

from src.constants import *

def clipped_relu(inputs):
    return Lambda(lambda y: K.minimum(K.maximum(y, 0), 20))(inputs)


def identity_block(input_tensor, kernel_size, filters, stage, block):   # next step try full-pre activation
    conv_name_base = 'res{}_{}_branch'.format(stage, block)

    x = Conv2D(filters,
                   kernel_size=1,
                   strides=1,
                   activation=None,
                   padding='same',
                   kernel_initializer='glorot_uniform',
                   kernel_regularizer=regularizers.l2(l=0.00001),
                   name=conv_name_base + '_conv1_1')(input_tensor)
    x = BatchNormalization(name=conv_name_base + '_conv1.1_bn')(x)
    x = clipped_relu(x)

    x = Conv2D(filters,
               kernel_size=kernel_size,
               strides=1,
               activation=None,
               padding='same',
               kernel_initializer='glorot_uniform',
               kernel_regularizer=regularizers.l2(l=0.00001),
               name=conv_name_base + '_conv3')(x)
    x = BatchNormalization(name=conv_name_base + '_conv3_bn')(x)
    x = clipped_relu(x)

    x = Conv2D(filters,
                   kernel_size=1,
                   strides=1,
                   activation=None,
                   padding='same',
                   kernel_initializer='glorot_uniform',
                   kernel_regularizer=regularizers.l2(l=0.00001),
                   name=conv_name_base + '_conv1_2')(x)
    x = BatchNormalization(name=conv_name_base + '_conv1.2_bn')(x)

    x = layers.add([x, input_tensor])
    x = clipped_relu(x)
    return x


def rescnn_model(input_shape=(NUM_FRAMES,64, 1),    #input_shape(32,32,3)
                        batch_size=BATCH_SIZE * TRIPLET_PER_BATCH , num_frames=NUM_FRAMES):
    # http://cs231n.github.io/convolutional-networks/
    # conv weights
    # #params = ks * ks * nb_filters * num_channels_input

    # Conv128-s
    # 5*5*128*128/2+128
    # ks*ks*nb_filters*channels/strides+bias(=nb_filters)

    # take 100 ms -> 4 frames.
    # if signal is 3 seconds, then take 100ms per 100ms and average out this network.
    # 8*8 = 64 features.

    # used to share all the layers across the inputs

    # num_frames = K.shape() - do it dynamically after.

    def conv_and_res_block(inp, filters, stage):
        conv_name = 'conv{}-s'.format(filters)
        o = Conv2D(filters,
                       kernel_size=5,
                       strides=2,
                       padding='same',
                       kernel_initializer='glorot_uniform',
                       kernel_regularizer=regularizers.l2(l=0.00001), name=conv_name)(inp)
        o = BatchNormalization(name=conv_name + '_bn')(o)
        o = clipped_relu(o)
        for i in range(3):
            o = identity_block(o, kernel_size=3, filters=filters, stage=stage, block=i)
        return o

    def cnn_component(inp):
        x_ = conv_and_res_block(inp, 64, stage=1)
        x_ = conv_and_res_block(x_, 128, stage=2)
        x_ = conv_and_res_block(x_, 256, stage=3)
        x_ = conv_and_res_block(x_, 512, stage=4)
        return x_

    inputs = Input(shape=input_shape)  # TODO the network should be definable without explicit batch shape
    x = cnn_component(inputs)  # .shape = (BATCH_SIZE , num_frames/8, 64/8, 512)
    x = Lambda(lambda y: K.reshape(y, (-1, math.ceil(num_frames / 16), 2048)), name='reshape')(x)
    x = Lambda(lambda y: K.mean(y, axis=1), name='average')(x)  #shape = (BATCH_SIZE, 512)
    x = Dense(512, name='affine')(x)  # .shape = (BATCH_SIZE , 512)
    x = Lambda(lambda y: K.l2_normalize(y, axis=1), name='ln')(x)

    model = Model(inputs, x, name='convolutional')
    print(model.summary())

    return model


if __name__ == '__main__':
    model = rescnn_model()
    # tf.keras.utils.plot_model(model, to_file="graph_hr.png", show_shapes=True, show_dtype=False,
    #                           show_layer_names=True, expand_nested=False, rankdir='LR')