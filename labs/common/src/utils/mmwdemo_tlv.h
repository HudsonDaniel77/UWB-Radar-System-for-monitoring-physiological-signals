/**
 *   @file  mmwdemo_tlvs.h
 *
 *   @brief
 *      This the header file which defines all TLV type numbers which are not included in SDK
 *
 *  \par
 *  NOTE:
 *      (C) Copyright 2018 Texas Instruments, Inc.
 *
 *  Redistribution and use in source and binary forms, with or without
 *  modification, are permitted provided that the following conditions
 *  are met:
 *
 *    Redistributions of source code must retain the above copyright
 *    notice, this list of conditions and the following disclaimer.
 *
 *    Redistributions in binary form must reproduce the above copyright
 *    notice, this list of conditions and the following disclaimer in the
 *    documentation and/or other materials provided with the
 *    distribution.
 *
 *    Neither the name of Texas Instruments Incorporated nor the names of
 *    its contributors may be used to endorse or promote products derived
 *    from this software without specific prior written permission.
 *
 *  THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
 *  "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
 *  LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR
 *  A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT
 *  OWNER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
 *  SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT
 *  LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE,
 *  DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY
 *  THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
 *  (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
 *  OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
 */
#ifndef MMWDEMO_TLVS_H
#define MMWDEMO_TLVS_H

#include <ti/demo/xwr68xx/mmw/include/mmw_output.h>

#ifdef __cplusplus
extern "C" {
#endif


// Generic TLV's
#define MMWDEMO_OUTPUT_MSG_SPHERICAL_POINTS                             1000

// Tracker TLV's
#define MMWDEMO_OUTPUT_MSG_TRACKERPROC_3D_TARGET_LIST                   1010
#define MMWDEMO_OUTPUT_MSG_TRACKERPROC_TARGET_INDEX                     1011
#define MMWDEMO_OUTPUT_MSG_TRACKERPROC_TARGET_HEIGHT                    1012

// Building Automation TLV's
#define MMWDEMO_OUTPUT_MSG_COMPRESSED_POINTS                            1020
#define MMWDEMO_OUTPUT_MSG_PRESCENCE_INDICATION                         1021

// Factory Automation and Robotics TLV's
#define MMWDEMO_OUTPUT_MSG_OCCUPANCY_STATE_MACHINE                      1030

#ifdef __cplusplus
}
#endif


/*!
 * @brief
 * Structure holds the message body to UART for the  Point Cloud
 *
 * @details
 * For each detected point, we report range, azimuth, and doppler
 */
typedef struct MmwDemo_output_message_compressedPoint_t
{
    /*! @brief Detected point elevation, in number of azimuthUnit */
    int8_t      elevation;
    /*! @brief Detected point azimuth, in number of azimuthUnit */
    int8_t      azimuth;
    /*! @brief Detected point doppler, in number of dopplerUnit */
    int16_t      doppler;
    /*! @brief Detected point range, in number of rangeUnit */
    uint16_t        range;
    /*! @brief Range detection SNR, in number of snrUnit */
    uint16_t       snr;

} MmwDemo_output_message_compressedPoint;

/*!
 * @brief
 * Structure holds the message body for the  Point Cloud units
 *
 * @details
 * Reporting units for range, azimuth, and doppler
 */
typedef struct MmwDemo_output_message_compressedPoint_unit_t
{
    /*! @brief elevation  reporting unit, in radians */
    float       elevationUnit;
    /*! @brief azimuth  reporting unit, in radians */
    float       azimuthUnit;
    /*! @brief Doppler  reporting unit, in m/s */
    float       dopplerUnit;
    /*! @brief range reporting unit, in m */
    float       rangeUnit;
    /*! @brief SNR  reporting unit, linear */
    float       snrUint;

} MmwDemo_output_message_compressedPoint_unit;

// Output struct for MMWDEMO_OUTPUT_MSG_OCCUPANCY_STATE_MACHINE
typedef struct MmwDemo_output_message_occStateMach_t
{
    uint32_t zoneStatusOutput;
} MmwDemo_output_message_occStateMach;

#endif /* MMWDEMO_TLVS_H */
