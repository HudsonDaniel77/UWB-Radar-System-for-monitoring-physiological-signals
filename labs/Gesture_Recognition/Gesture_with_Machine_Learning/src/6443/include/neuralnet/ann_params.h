/*
 * ann_params.h
 *
 * Header file that points to the ANN coefficients
 *
 */

#ifndef INCLUDE_NEURALNET_ANN_PARAMS_H_
#define INCLUDE_NEURALNET_ANN_PARAMS_H_

         {
            #include "include/neuralnet/mean.h"
         }, //mean

         {
            #include "include/neuralnet/std.h"
         }, //standard deviation

         {
            #include "include/neuralnet/b0.h"
         }, //B_0

         {
            #include "include/neuralnet/b1.h"
         }, //B_1

         {
            #include "include/neuralnet/b2.h"
         }, //B_2

         {
            #include "include/neuralnet/w0.h"
         }, //W_0

         {
            #include "include/neuralnet/w1.h"
         }, //W_1

         {
            #include "include/neuralnet/w2.h"
         }, //W_2

         { 0 }, //op_layer1
         { 0 }, //op_layer2
         { 0 }, //op_layer3
         { 0 }  // op_prob

#endif /* INCLUDE_NEURALNET_ANN_PARAMS_H_ */
