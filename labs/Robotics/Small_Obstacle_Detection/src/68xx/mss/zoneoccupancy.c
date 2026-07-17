/*
 *   @file zoneoccupancy.c
 *
 *   @brief
 *      Mmw (Milli-meter wave) Zone Occupancy
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

#include "zoneoccupancy.h"
#include "mmw_mss.h"

static bool ZoneOcc_isPointInZone(DPIF_PointCloudCartesian point, MmwDemo_ZoneCfg zone)
{
    if (point.x >= zone.xMin && point.x <= zone.xMax)
    {
        if (point.y >= zone.yMin && point.y <= zone.yMax)
        {
            if (point.z >= zone.zMin && point.z <= zone.zMax)
            {
                return true;
            }
        }
    }
    return false;
}

int32_t ZoneOcc_updateStateMachine(MmwDemo_OccStateMachCfg *occStateMachCfg, DPC_ObjectDetection_ExecuteResult *dpcResults)
{
    DPIF_PointCloudCartesian *objOut;
    DPIF_PointCloudSideInfo *objOutSideInfo;
    int32_t errCode;
    uint32_t numPoints;
    uint8_t pointIdx;
    uint8_t zoneIdx;

    if (occStateMachCfg == NULL || dpcResults == NULL)
    {
        return -1;
    }

    // Get info from DPC Results since addresses will need to be translated
    numPoints =  dpcResults->numObjOut;

    objOut = (DPIF_PointCloudCartesian *) SOC_translateAddress((uint32_t)dpcResults->objOut,
                                                     SOC_TranslateAddr_Dir_FROM_OTHER_CPU,
                                                     &errCode);
    DebugP_assert ((uint32_t)objOut != SOC_TRANSLATEADDR_INVALID);

    objOutSideInfo = (DPIF_PointCloudSideInfo *) SOC_translateAddress((uint32_t)dpcResults->objOutSideInfo,
                                                 SOC_TranslateAddr_Dir_FROM_OTHER_CPU,
                                                 &errCode);
    DebugP_assert ((uint32_t)objOutSideInfo != SOC_TRANSLATEADDR_INVALID);

    // Initialize each zone's number of points and avg SNR
    for (zoneIdx = 0; zoneIdx < occStateMachCfg->numZones; zoneIdx++)
    {
        occStateMachCfg->zones[zoneIdx].numPoints = 0;
        occStateMachCfg->zones[zoneIdx].avgSNR = 0;
    }

    // Check every point for what zone they may fall into
    for (pointIdx = 0; pointIdx < numPoints; pointIdx++)
    {
        // Check each zone for whether the zone contains the point
        for (zoneIdx = 0; zoneIdx < occStateMachCfg->numZones; zoneIdx++)
        {
            if (ZoneOcc_isPointInZone(objOut[pointIdx], occStateMachCfg->zones[zoneIdx]))
            {
                // Calculate new average SNR
                // NewAvg = (OldAvg * OldNumPoints + NewSNR)/NewNumPoints
                occStateMachCfg->zones[zoneIdx].avgSNR = (occStateMachCfg->zones[zoneIdx].avgSNR * occStateMachCfg->zones[zoneIdx].numPoints + objOutSideInfo[pointIdx].snr) / (occStateMachCfg->zones[zoneIdx].numPoints + 1);
                occStateMachCfg->zones[zoneIdx].numPoints++;
                break;
            }
        }
    }
    // Move between states based on avg snr and num points in each zone
    for (zoneIdx = 0; zoneIdx < occStateMachCfg->numZones; zoneIdx++)
    {
        // Zone not currently in occupied state
        if (occStateMachCfg->zones[zoneIdx].isOccupied == false)
        {
            if ((occStateMachCfg->zones[zoneIdx].numPoints >= occStateMachCfg->pointsEntryThreshold) && (occStateMachCfg->zones[zoneIdx].avgSNR >= occStateMachCfg->snrEntryThreshold))
            {
                occStateMachCfg->zones[zoneIdx].entryFrameCount++;
            }
            else
            {
                occStateMachCfg->zones[zoneIdx].entryFrameCount = 0;
            }

            if (occStateMachCfg->zones[zoneIdx].entryFrameCount >= occStateMachCfg->frameEntryThreshold)
            {
                occStateMachCfg->zones[zoneIdx].isOccupied = true;
                occStateMachCfg->zones[zoneIdx].exitFrameCount = 0;
            }
        }
        // Zone is currently in occupied state
        else
        {
            // Maintain occupied state and reset the counter
            if ((occStateMachCfg->zones[zoneIdx].numPoints >= occStateMachCfg->pointsMaintainThreshold) && (occStateMachCfg->zones[zoneIdx].avgSNR >= occStateMachCfg->snrMaintainThreshold))
            {
                occStateMachCfg->zones[zoneIdx].exitFrameCount = 0;
            }
            // Number of points is less than number to forget
            else if (occStateMachCfg->zones[zoneIdx].numPoints <= occStateMachCfg->pointsExitThreshold)
            {
                // Frame timer has expired, enter unoccupied state
                if (occStateMachCfg->zones[zoneIdx].exitFrameCount >= occStateMachCfg->frameExitThreshold)
                {
                    occStateMachCfg->zones[zoneIdx].isOccupied = false;
                    occStateMachCfg->zones[zoneIdx].exitFrameCount = 0;
                }
                // Increment the timer
                else
                {
                    occStateMachCfg->zones[zoneIdx].exitFrameCount++;
                }
            }
            else
            {
                // Avoid decrementing the counter to a negative number
                if (occStateMachCfg->zones[zoneIdx].exitFrameCount > 0)
                {
                    occStateMachCfg->zones[zoneIdx].exitFrameCount--;
                }
            }
        }
    }
    return 0;
}

uint32_t ZoneOcc_getOutput(MmwDemo_OccStateMachCfg *occStateMachCfg)
{
    uint32_t zoneIdx;
    uint32_t occStatusMask = 0;

    if (occStateMachCfg == NULL)
    {
        return 0;
    }
    for (zoneIdx = 0; zoneIdx < occStateMachCfg->numZones; zoneIdx++)
    {
        occStatusMask |= occStateMachCfg->zones[zoneIdx].isOccupied << zoneIdx;
    }
    return occStatusMask;
}

