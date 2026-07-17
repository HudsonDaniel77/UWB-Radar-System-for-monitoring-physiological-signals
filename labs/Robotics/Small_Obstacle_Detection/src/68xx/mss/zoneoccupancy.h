/**
 *   @file  zoneoccupancy.h
 *
 *   @brief
 *      Header file for MMW zone occupancy
 *
 *  \par
 *  NOTE:
 *      (C) Copyright 2016 Texas Instruments, Inc.
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

#ifndef ZONEOCCUPANCY_H_
#define ZONEOCCUPANCY_H_

#include <ti/common/sys_common.h>
#include <ti/demo/xwr68xx/mmw/include/mmw_output.h>

#define MMWDEMO_MAX_ZONES 2

/*!
 * @brief
 * Structure holds info on occupancy zones
 *
 * @details
 *  The structure holds occupancy zone configuration.
 */
typedef struct MmwDemo_ZoneCfg_t
{
    float           xMin;

    float           xMax;

    float           yMin;

    float           yMax;

    float           zMin;

    float           zMax;

    uint8_t         numPoints;

    float           avgSNR;

    bool            isOccupied;

    uint8_t         entryFrameCount;

    uint8_t         exitFrameCount;

} MmwDemo_ZoneCfg;

/*!
 * @brief
 * Structure holds info on occupancy state machine
 *
 * @details
 *  The structure holds occupancy state machine configuration.
 */
typedef struct MmwDemo_OccStateMachCfg_t
{
    uint8_t         numZones;

    uint8_t         pointsEntryThreshold;

    uint8_t         snrEntryThreshold;

    uint8_t         frameEntryThreshold;

    uint8_t         pointsMaintainThreshold;

    uint8_t         snrMaintainThreshold;

    uint8_t         pointsExitThreshold;

    uint8_t         frameExitThreshold;

    MmwDemo_ZoneCfg zones[MMWDEMO_MAX_ZONES];

} MmwDemo_OccStateMachCfg;


// Function prototypes
int32_t ZoneOcc_updateStateMachine(MmwDemo_OccStateMachCfg *occStateMachCfg, DPC_ObjectDetection_ExecuteResult *dpcResults);
uint32_t ZoneOcc_getOutput(MmwDemo_OccStateMachCfg *occStateMachCfg);

#endif /* ZONEOCCUPANCY_H_ */
