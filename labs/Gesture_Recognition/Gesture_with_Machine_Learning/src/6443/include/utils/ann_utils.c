/*
 * ann_utils.c
 *
 */


#include <stdint.h>
#include <math.h>

#include "include/utils/ann_utils.h"

/*
@Brief: x1 is the pointer to first input whose length is len
@Brief: x2 is the pointer to second input whose length is len
This function computes the inner product between two vectors
*/
float annUtils_computeInnerprod(float x1[], float x2[], unsigned const int len)
{
    float prod = 0;
    uint32_t i=0;

    for(i=0; i<len; i++)
    {
        prod += x1[i]*x2[i];
    }
    return prod;
}

/*
This function computes the relu activation max(0,inp)
*/
void annUtils_reluActivation(float inp[], unsigned const int len)
{
    uint32_t i=0;
    for(i=0; i<len; i++)
    {
        if(inp[i] <= 0.0f)
        {
            inp[i] = 0.0f;
        }
    }

}

/*
This is stable implementation of SOFT-MAX
*/
void annUtils_softMax(float inp[],  unsigned const int len, float prob[])
{
    /* find the max */
    float maxval = inp[0];
    float sum = 0.0f;
    uint32_t i;
    for(i=1; i<len; i++)
    {
        if(inp[i] > maxval)
            maxval = inp[i];
    }
    /* subtract max from all entries in input */
    for(i=0; i<len; i++)
    {
        inp[i] = (float) exp((double) (inp[i] - maxval)); // exp() expects double type as input and return double type as output
        sum += inp[i];
    }
    for(i=0; i<len; i++)
    {
        prob[i] = inp[i]/sum;
    }
}

void annUtils_inference(float *input, ANN_struct_t* pANN_struct_t)
{

    float prod;
    uint32_t i=0;

    /* compute Layer 1 output */
    for(i=0; i<NUM_NODES_FIRST_LAYER; i++)
    {
        pANN_struct_t->op_layer1[i] = pANN_struct_t->b_0[i]; // initialize with bias value
        prod = annUtils_computeInnerprod(input, &pANN_struct_t->W_0[i][0], INP_DIM);
        pANN_struct_t->op_layer1[i] += prod;
    }
    /* activation layer */
    annUtils_reluActivation(pANN_struct_t->op_layer1, NUM_NODES_FIRST_LAYER);

    /* compute Layer2 output */
    for(i=0; i<NUM_NODES_SECOND_LAYER; i++)
    {
        pANN_struct_t->op_layer2[i] = pANN_struct_t->b_1[i]; // initialize with bias value
        prod = annUtils_computeInnerprod(pANN_struct_t->op_layer1, &pANN_struct_t->W_1[i][0], NUM_NODES_FIRST_LAYER);
        pANN_struct_t->op_layer2[i] += prod;
    }
    /* activation layer */
    annUtils_reluActivation(pANN_struct_t->op_layer2, NUM_NODES_SECOND_LAYER);

    /* compute Layer3 output */
    for(i=0; i<NUM_NODES_THIRD_LAYER; i++)
    {
        /* initialize with bias value */
        pANN_struct_t->op_layer3[i] = pANN_struct_t->b_2[i];
        prod = annUtils_computeInnerprod(pANN_struct_t->op_layer2, &pANN_struct_t->W_2[i][0], NUM_NODES_SECOND_LAYER);
        pANN_struct_t->op_layer3[i] += prod;
    }

    /* soft-max layer */
    annUtils_softMax(pANN_struct_t->op_layer3, NUM_NODES_THIRD_LAYER, pANN_struct_t->prob);
}
