/*
 * ann_utils.h
 *
 */

#ifndef INCLUDE_UTILS_ANN_UTILS_H_
#define INCLUDE_UTILS_ANN_UTILS_H_

#include "gesture.h"

/*
 * This function computes the inner product between two vectors
*/
float annUtils_computeInnerprod(float x1[], float x2[], unsigned const int len);

void annUtils_reluActivation(float inp[], unsigned const int len);

void annUtils_softMax(float inp[],  unsigned const int len, float prob[]);

void annUtils_inference(float *input, ANN_struct_t* pANN_struct_t);

#endif /* INCLUDE_UTILS_ANN_UTILS_H_ */
