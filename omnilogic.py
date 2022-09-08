#!/usr/bin/env python3

import socket
import struct
import random
import time
import zlib
import os
import xml.etree.ElementTree as ET
import logging
from typing import Literal, Union

REQUEST_CONFIGURATION_MESSAGE_TYPE = 1
SET_FILTER_SPEED_MESSAGE_TYPE = 9
REQUEST_LOG_CONFIG_MESSAGE_TYPE = 31
SET_EQUIPMENT_MESSAGE_TYPE = 164
CREATE_SCHEDULE_MESSAGE_TYPE = 230
DELETE_SCHEDULE_MESSAGE_TYPE = 231
MSP_LEADMESSAGE_MESSAGE_TYPE = 1998
MSP_BLOCKMESSAGE_MESSAGE_TYPE = 1999
MSP_CONFIGURATIONUPDATE_MESSAGE_TYPE = 1003
GETTELEMETRY_MESSAGE_TYPE = 300
GETALARMLIST_MESSAGE_TYPE = 304
SET_STANDALONE_LIGHT_SHOW_MESSAGE_TYPE = 308
GET_FILTER_DIAGNOSTIC_INFO_MESSAGE_TYPE = 386
MSP_TELEMETRYUPDATE_MESSAGE_TYPE = 1004
XMLACK_MESSAGE_TYPE = 0000
HANDSHAKE_MESSAGE_TYPE = 1000
ACK_MESSAGE_TYPE = 1002

class OmniLogicRequest:
    HEADER_FORMAT = "!LQ4sLBBBB"
    def __init__(self, msgId, msgType, extraData="", clientType=1):
        self.msgId = msgId
        self.msgType = msgType
        self.clientType = clientType
        self.extraData = bytes(extraData, "utf-8")
        # self.extraData = extraData

        self.version = "1.19".encode("ascii")

    def toBytes(self):
        retval = struct.pack(OmniLogicRequest.HEADER_FORMAT,
                             self.msgId,                  # Msg id
                             int(time.time_ns()/(10**9)), # Timestamp
                             bytes(self.version),         # version string
                             self.msgType,                # OpID/msgType
                             self.clientType,             # Client type
                             0, 0, 0)                     # reserved
        # logging.debug(retval+self.extraData)
        return retval + self.extraData

    @staticmethod
    def fromBytes(data):
        # split the header and data
        header = data[0:24]
        rdata = data[24:]

        msgId, tstamp, vers, msgType, clientType, res1, compressed, res3 = struct.unpack(OmniLogicRequest.HEADER_FORMAT, header)
        return msgId, tstamp, vers, msgType, clientType, res1, compressed, res3, rdata


class OmniLogicAPI:
    def __init__(self, controllerIpAndPort, senderPort, responseTimeout):
        self.controllerIpAndPort = controllerIpAndPort
        self.senderPort = senderPort
        self.responseTimeout = responseTimeout

    def getSock(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.bind(("0.0.0.0", self.senderPort))
        return sock

    def getAlarmList(self):
        sock = self.getSock()

        bodyElement = ET.Element('Request', {'xmlns': 'http://nextgen.hayward.com/api'})

        nameElement = ET.SubElement(bodyElement, 'Name')
        nameElement.text = "GetAllAlarmList"

        reqBody = ET.tostring(bodyElement, xml_declaration=True, encoding='unicode')
        self._sendRequest(sock, GETALARMLIST_MESSAGE_TYPE, reqBody)

        data = self._receiveFile(sock)
        return data

    def getConfig(self):
        sock = self.getSock()

        bodyElement = ET.Element('Request', {'xmlns': 'http://nextgen.hayward.com/api'})

        nameElement = ET.SubElement(bodyElement, 'Name')
        nameElement.text = "RequestConfiguration"

        reqBody = ET.tostring(bodyElement, xml_declaration=True, encoding='unicode')
        self._sendRequest(sock, REQUEST_CONFIGURATION_MESSAGE_TYPE, reqBody)

        data = self._receiveFile(sock)
        return data

    def getFilterDiagnostics(self, poolId: int, equipmentId: int):
        """getDiagnostics handles sending a GetUIFilterDiagnosticInfo XML API call to the Hayward Omni pool controller

        Args:
            poolId (int): The Pool/BodyOfWater ID that you want to address
            equipmentId (int): Which equipmentID within that Pool to address

        Returns:
            _type_: _description_
        """
        sock = self.getSock()

        bodyElement = ET.Element('Request', {'xmlns': 'http://nextgen.hayward.com/api'})

        nameElement = ET.SubElement(bodyElement, 'Name')
        nameElement.text = "GetUIFilterDiagnosticInfo"
        parametersElement = ET.SubElement(bodyElement, 'Parameters')
        parameter = ET.SubElement(parametersElement, 'Parameter', name="PoolID", dataType="int")
        parameter.text = str(poolId)
        parameter = ET.SubElement(parametersElement, 'Parameter', name="EquipmentID", dataType="int")
        parameter.text = str(equipmentId)

        reqBody = ET.tostring(bodyElement, xml_declaration=True, encoding='unicode')
        self._sendRequest(sock, REQUEST_CONFIGURATION_MESSAGE_TYPE, reqBody)

        data = self._receiveFile(sock)
        return data

    def getLogConfig(self):
        sock = self.getSock()

        self._sendRequest(sock, REQUEST_LOG_CONFIG_MESSAGE_TYPE)

        data = self._receiveFile(sock)
        return data

    def getTelemetry(self):
        sock = self.getSock()

        bodyElement = ET.Element('Request', {'xmlns': 'http://nextgen.hayward.com/api'})

        nameElement = ET.SubElement(bodyElement, 'Name')
        nameElement.text = "RequestTelemetryData"

        reqBody = ET.tostring(bodyElement, xml_declaration=True, encoding='unicode')
        self._sendRequest(sock, GETTELEMETRY_MESSAGE_TYPE, reqBody)

        data = self._receiveFile(sock)
        return data

    # pylint: disable=too-many-arguments,too-many-locals
    def setEquipment(self, poolId: int, equipmentId: int, isOn: Union[int,bool],
        isCountDownTimer: bool=False, startTimeHours: int=0, startTimeMinutes: int=0,
        endTimeHours: int=0, endTimeMinutes: int=0, daysActive: int=0, recurring: bool=False):
        """setEquipment handles sending a SetUIEquipmentCmd XML API call to the Hayward Omni pool controller

        Args:
            poolId (int): The Pool/BodyOfWater ID that you want to address
            equipmentId (int): Which equipmentID within that Pool to address
            isOn (Union[int,bool]): For most equipment items, True/False to turn on/off.
                For Variable Speed Pumps, you can optionally provide an int from 0-100 to set the speed percentage with 0 being Off.
            isCountDownTimer (bool, optional): For potential future use, included to be "API complete". Defaults to False.
            startTimeHours (int, optional): For potential future use, included to be "API complete". Defaults to 0.
            startTimeMinutes (int, optional): For potential future use, included to be "API complete". Defaults to 0.
            endTimeHours (int, optional): For potential future use, included to be "API complete". Defaults to 0.
            endTimeMinutes (int, optional): For potential future use, included to be "API complete". Defaults to 0.
            daysActive (int, optional): For potential future use, included to be "API complete". Defaults to 0.
            recurring (bool, optional): For potential future use, included to be "API complete". Defaults to False.
        """
        sock = self.getSock()

        bodyElement = ET.Element('Request', {'xmlns': 'http://nextgen.hayward.com/api'})

        nameElement = ET.SubElement(bodyElement, 'Name')
        nameElement.text = "SetUIEquipmentCmd"

        parametersElement = ET.SubElement(bodyElement, 'Parameters')
        parameter = ET.SubElement(parametersElement, 'Parameter', name="PoolID", dataType="int")
        parameter.text = str(poolId)
        parameter = ET.SubElement(parametersElement, 'Parameter', name="EquipmentID", dataType="int")
        parameter.text = str(equipmentId)
        parameter = ET.SubElement(parametersElement, 'Parameter', name="IsOn", dataType="int")
        parameter.text = str(int(isOn))
        parameter = ET.SubElement(parametersElement, 'Parameter', name="IsCountDownTimer", dataType="bool")
        parameter.text = str(int(isCountDownTimer))
        parameter = ET.SubElement(parametersElement, 'Parameter', name="StartTimeHours", dataType="int")
        parameter.text = str(startTimeHours)
        parameter = ET.SubElement(parametersElement, 'Parameter', name="StartTimeMinutes", dataType="int")
        parameter.text = str(startTimeMinutes)
        parameter = ET.SubElement(parametersElement, 'Parameter', name="EndTimeHours", dataType="int")
        parameter.text = str(endTimeHours)
        parameter = ET.SubElement(parametersElement, 'Parameter', name="EndTimeMinutes", dataType="int")
        parameter.text = str(endTimeMinutes)
        parameter = ET.SubElement(parametersElement, 'Parameter', name="DaysActive", dataType="int")
        parameter.text = str(daysActive)
        parameter = ET.SubElement(parametersElement, 'Parameter', name="Recurring", dataType="bool")
        parameter.text = str(int(recurring))

        reqBody = ET.tostring(bodyElement, xml_declaration=True, encoding='unicode')
        self._sendRequest(sock, SET_EQUIPMENT_MESSAGE_TYPE, reqBody)

    def setFilterSpeed(self, poolId: int, equipmentId: int, speed: int):
        """setFilterSpeed handles sending a SetUIFilterSpeedCmd XML API call to the Hayward Omni pool controller

        Args:
            poolId (int): The Pool/BodyOfWater ID that you want to address
            equipmentId (int): Which equipmentID within that Pool to address
            speed (int): Speed value from 0-100 to set the filter to.  A value of 0 will turn the filter off.
        """
        sock = self.getSock()

        bodyElement = ET.Element('Request', {'xmlns': 'http://nextgen.hayward.com/api'})

        nameElement = ET.SubElement(bodyElement, 'Name')
        nameElement.text = "SetUIFilterSpeedCmd"

        parametersElement = ET.SubElement(bodyElement, 'Parameters')
        parameter = ET.SubElement(parametersElement, 'Parameter', name="PoolID", dataType="int")
        parameter.text = str(poolId)
        parameter = ET.SubElement(parametersElement, 'Parameter', name="FilterID", dataType="int", alias="EquipmentID")
        parameter.text = str(equipmentId)
        # NOTE: Despite the API calling it RPM here, the speed value is a percentage from 1-100
        parameter = ET.SubElement(parametersElement, 'Parameter', name="Speed", dataType="int", unit="RPM", alias="Data")
        parameter.text = str(speed)

        reqBody = ET.tostring(bodyElement, xml_declaration=True, encoding='unicode')
        self._sendRequest(sock, SET_FILTER_SPEED_MESSAGE_TYPE, reqBody)

    def setLightShow(self, poolId: int, equipmentId: int, show: int, speed: Literal[0,1,2,3,4,5,6,7,8]=4, brightness: Literal[0,1,2,3,4]=4,
        reserved: int=0, isCountDownTimer: bool=False, startTimeHours: int=0, startTimeMinutes: int=0, endTimeHours: int=0,
        endTimeMinutes: int=0, daysActive: int=0, recurring: bool=False):
        """setLightShow handles sending a SetStandAloneLightShow XML API call to the Hayward Omni pool controller

        Args:
            poolId (int): The Pool/BodyOfWater ID that you want to address
            equipmentId (int): Which equipmentID within that Pool to address
            show (int): ID of the light show to display
            speed (Literal[0,1,2,3,4,5,6,7,8], optional): Speed to animate the show. Defaults to 4.  0-8 which map to:
                0: 1/16th
                1: 1/8th
                2: 1/4
                3: 1/2
                4: 1x
                5: 2x
                6: 4x
                7: 8x
                8: 16x
            brightness (Literal[0,1,2,3,4], optional): How bright should the light be. Defaults to 4. 0-4 which map to:
                0: 20%
                1: 40%
                2: 60%
                3: 80%
                4: 100%
            reserved (int, optional): Reserved. Defaults to 0.
            isCountDownTimer (bool, optional): For potential future use, included to be "API complete". Defaults to False.
            startTimeHours (int, optional): For potential future use, included to be "API complete". Defaults to 0.
            startTimeMinutes (int, optional): For potential future use, included to be "API complete". Defaults to 0.
            endTimeHours (int, optional): For potential future use, included to be "API complete". Defaults to 0.
            endTimeMinutes (int, optional): For potential future use, included to be "API complete". Defaults to 0.
            daysActive (int, optional): For potential future use, included to be "API complete". Defaults to 0.
            recurring (bool, optional): For potential future use, included to be "API complete". Defaults to False.
        """
        sock = self.getSock()

        bodyElement = ET.Element('Request', {'xmlns': 'http://nextgen.hayward.com/api'})

        nameElement = ET.SubElement(bodyElement, 'Name')
        nameElement.text = "SetStandAloneLightShow"

        parametersElement = ET.SubElement(bodyElement, 'Parameters')
        parameter = ET.SubElement(parametersElement, 'Parameter', name="PoolID", dataType="int")
        parameter.text = str(poolId)
        parameter = ET.SubElement(parametersElement, 'Parameter', name="LightID", dataType="int", alias="EquipmentID")
        parameter.text = str(equipmentId)
        parameter = ET.SubElement(parametersElement, 'Parameter', name="Show", dataType="byte")
        parameter.text = str(show)
        parameter = ET.SubElement(parametersElement, 'Parameter', name="Speed", dataType="byte")
        parameter.text = str(speed)
        parameter = ET.SubElement(parametersElement, 'Parameter', name="Brightness", dataType="byte")
        parameter.text = str(brightness)
        parameter = ET.SubElement(parametersElement, 'Parameter', name="Reserved", dataType="byte")
        parameter.text = str(reserved)
        parameter = ET.SubElement(parametersElement, 'Parameter', name="IsCountDownTimer", dataType="bool")
        parameter.text = str(int(isCountDownTimer))
        parameter = ET.SubElement(parametersElement, 'Parameter', name="StartTimeHours", dataType="int")
        parameter.text = str(startTimeHours)
        parameter = ET.SubElement(parametersElement, 'Parameter', name="StartTimeMinutes", dataType="int")
        parameter.text = str(startTimeMinutes)
        parameter = ET.SubElement(parametersElement, 'Parameter', name="EndTimeHours", dataType="int")
        parameter.text = str(endTimeHours)
        parameter = ET.SubElement(parametersElement, 'Parameter', name="EndTimeMinutes", dataType="int")
        parameter.text = str(endTimeMinutes)
        parameter = ET.SubElement(parametersElement, 'Parameter', name="DaysActive", dataType="int")
        parameter.text = str(daysActive)
        parameter = ET.SubElement(parametersElement, 'Parameter', name="Recurring", dataType="bool")
        parameter.text = str(int(recurring))

        reqBody = ET.tostring(bodyElement, xml_declaration=True, encoding='unicode')
        self._sendRequest(sock, SET_STANDALONE_LIGHT_SHOW_MESSAGE_TYPE, reqBody)


    def _sendRequest(self, sock, msgType, extraData=""):
        logging.debug("Message Type: %d, Request Body: %s", msgType, extraData)

        # Good security practice, random msgId's.
        msgId = random.randrange(2**32)

        # If we are speaking the XML API, it seems like we need clientType 0, otherwise we need clientType 1
        clientType = 0 if extraData != "" else 1

        # The Hayward API terminates it's messages with a null character
        extraData += "\x00" if extraData != "" else ""

        request = OmniLogicRequest(msgId, msgType, extraData, clientType)

        sock.sendto(request.toBytes(), self.controllerIpAndPort)

        # wait for the ACK resp
        self._waitForData(sock, msgId)

    def _receiveFile(self, sock):
        # This handles when we get a LeadMessage. if the length of the file we
        # requested is < 1024 bytes, then all the data is in this first packet
        # Otherwise we need to read "MsgBlockCount" number of BlockMessages.

        # Receive our first message
        msgId, _, _, msgType, _, _, compressed, _, data = self._recv(sock)
        # Send an ack
        self._sendAck(sock, msgId)

        # Check if the 23rd bit of the header (compressed bit) was a 1
        # There are also some messages that are ALWAYS compressed although they do not return a 1 in their LeadMessage
        msgCompressed = compressed == 1 or msgType in [MSP_TELEMETRYUPDATE_MESSAGE_TYPE]

        # If the response is too large, the controller will send a LeadMessage indicating how many follow-up messages will be sent
        if msgType == MSP_LEADMESSAGE_MESSAGE_TYPE:
            # Parse XML
            root = ET.fromstring(data[:-1]) #strip trailing \x00
            blockCount = int(root.findall(".//*[@name='MsgBlockCount']")[0].text)

            # Wait for the block data data
            retval = b''
            # If we received a LeadMessage, continue to receive messages until we have all of our data
            for _ in range(blockCount):
                msgId, _, _, msgType, _, _, _, _, data = self._recv(sock)
                self._sendAck(sock, msgId)
                # remove an 8 byte header to get to the payload data
                retval += data[8:]
        # If we did not receive a LeadMessage, but the message is compressed anyway...
        elif msgCompressed:
            retval = data
        # A short response, no LeadMessage and no compression...
        else:
            retval = data[8:]

        # Decompress the returned data if necessary
        if msgCompressed:
            compBytes = bytes.fromhex(retval.hex())
            retval = zlib.decompress(compBytes)

        # return retval
        return retval.decode('utf-8')

    def _sendAck(self, sock, msgId):

        bodyElement = ET.Element('Request', {'xmlns': 'http://nextgen.hayward.com/api'})
        nameElement = ET.SubElement(bodyElement, 'Name')
        nameElement.text = "Ack"

        reqBody = ET.tostring(bodyElement, xml_declaration=True, encoding='unicode')
        request = OmniLogicRequest(msgId, XMLACK_MESSAGE_TYPE, reqBody, 0)

        sock.sendto(request.toBytes(), self.controllerIpAndPort)

    def _recv(self, sock):
        resp = sock.recvfrom(65565)
        msgId, tstamp, vers, msgType, clientType, res1, compressed, res3, data = OmniLogicRequest.fromBytes(resp[0])
        return msgId, tstamp, vers, msgType, clientType, res1, compressed, res3, data

    def _waitForData(self, sock, msgId):
        respMsgId = -1
        start = time.time()
        sock.settimeout(0.5)
        while respMsgId != msgId and time.time() < start + self.responseTimeout:
            try:
                respMsgId, tstamp, vers, msgType, clientType, res1, compressed, res3, data = self._recv(sock)
                if msgId == respMsgId:
                    return respMsgId, tstamp, vers, msgType, clientType, res1, compressed, res3, data
            except socket.timeout:
                pass
        raise Exception() # timeout

if __name__ == "__main__":
    logging.basicConfig(format='%(asctime)s %(levelname)s: %(message)s', level=logging.DEBUG)
    # logging.basicConfig(format='%(asctime)s %(levelname)s: %(message)s', level=logging.WARNING)
    api = OmniLogicAPI((os.environ.get('OMNILOGIC_HOST'), 10444), 10444, 5)

    # cfg = api.getConfig()
    # print(cfg)

    #logConfig = api.getLogConfig()
    #print(logConfig)

    telem = api.getTelemetry()
    print(telem)

    # telem = api.getAlarmList()
    # print(telem)

    # equip = api.setEquipment(1, 2, 0)
    # equip = api.setFilterSpeed(1, 2, 0)
    # light = api.setLightShow(1, 4, 12)
    # # print(equip)

    # time.sleep(1.5)
    # telem = api.getTelemetry()
    # print(telem)


    # Nums in the request that get an ack, but nothing else:
    # 300
    # 304
    # 305
    # 977
    # 1003