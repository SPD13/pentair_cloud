from pycognito import Cognito
from homeassistant.core import HomeAssistant
import boto3
import requests
from logging import Logger
from requests_aws4auth import AWS4Auth
from homeassistant.components.light import ATTR_BRIGHTNESS, PLATFORM_SCHEMA, LightEntity
import time
from .const import DEBUG_INFO

AWS_REGION = "us-west-2"
AWS_USER_POOL_ID = "us-west-2_lbiduhSwD"
AWS_CLIENT_ID = "3de110o697faq7avdchtf07h4v"
AWS_IDENTITY_POOL_ID = "us-west-2:6f950f85-af44-43d9-b690-a431f753e9aa"
AWS_COGNITO_ENDPOINT = "cognito-idp.us-west-2.amazonaws.com"
PENTAIR_ENDPOINT = "https://api.pentair.cloud"
PENTAIR_USER_PROFILE_PATH = "/user/user-service/common/profilev2"
PENTAIR_DEVICES_PATH = "/device/device-service/user/devices"
PENTAIR_DEVICES_2_PATH = "/device2/device2-service/user/device"
PENTAIR_DEVICE_SERVICE_PATH = "/device/device-service/user/device/"
UPDATE_MIN_SECONDS = 60  # Minimum time between two update requests
PROGRAM_START_MIN_SECONDS = 30  # Minimum time between two requests to start a program


class PentairPumpProgram:
    def __init__(
        self, id: int, name: str, program_type: int, running_program: int
    ) -> None:
        self.id = id
        self.name = name
        self.program_type = program_type  # 0=Schedule, 1=Interval, 2=Manual
        if running_program == id:
            self.running = True
        else:
            self.running = False

    def get_start_value(self) -> int:
        return 3
        # if self.program_type == 0:
        #    return 3
        # else:
        #    return 2

    def get_stop_value(self) -> int:
        return 2
        # if self.program_type == 0:
        #    return 2
        # else:
        #    return 0


class PentairDevice:
    def __init__(self, LOGGER: Logger, pentair_device_id: str, nickname: str) -> None:
        self.LOGGER = LOGGER
        self.pentair_device_id = pentair_device_id
        self.nickname = nickname
        self.status = False
        self.last_program_start = None
        self.active_program = None
        self.programs = []

    def update_program(
        self, id: int, name: str, program_type: int, running_program: int
    ) -> None:
        exists = False
        for program in self.programs:
            if program.id == id:  # update
                exists = True
                program.name = name
                program.program_type = program_type
                if program.id == running_program:
                    program.running = True
                else:
                    program.running = False
                if DEBUG_INFO:
                    self.LOGGER.info(
                        "Update program for device "
                        + self.pentair_device_id
                        + " / "
                        + str(id)
                        + " - "
                        + name
                        + " ("
                        + str(program.running)
                        + ")"
                    )
        if exists == False:
            self.programs.append(
                PentairPumpProgram(id, name, program_type, running_program)
            )
            if DEBUG_INFO:
                self.LOGGER.info(
                    "Found new program for device "
                    + self.pentair_device_id
                    + " / "
                    + str(id)
                    + " - "
                    + name
                )


class PentairCloudHub:
    global AWS_USER_POOL_ID
    global AWS_CLIENT_ID
    global AWS_REGION
    global AWS_COGNITO_ENDPOINT
    global AWS_USER_POOL_ID
    global AWS_IDENTITY_POOL_ID
    global PENTAIR_ENDPOINT
    global PENTAIR_DEVICES_PATH
    global PENTAIR_DEVICES_2_PATH
    global PENTAIR_DEVICE_SERVICE_PATH
    global UPDATE_MIN_SECONDS
    global PROGRAM_START_MIN_SECONDS

    def __init__(
        self,
        LOGGER: Logger,
    ) -> None:
        self.cognito_client = None
        self.LOGGER = LOGGER
        self.AWS_TOKEN = None
        self.AWS_IDENTITY_ID = None
        self.AWS_ACCESS_KEY_ID = None
        self.AWS_SECRET_ACCESS_KEY = None
        self.AWS_SESSION_TOKEN = None
        self.last_update = None
        self.username = None
        self.password = None
        self.devices = []

    def get_cognito_client(self, usr: str) -> Cognito:
        return Cognito(AWS_USER_POOL_ID, AWS_CLIENT_ID, username=usr)

    def get_devices(self) -> list[PentairDevice]:
        return self.devices

    def populate_AWS_token(self) -> None:
        if self.cognito_client is not None:
            self.cognito_client.check_token()
            new_token = self.cognito_client.get_user()._metadata["id_token"]
            if self.AWS_TOKEN != new_token:  # Token has been refreshed
                self.AWS_TOKEN = new_token
                self.populate_AWS_and_data_fields()

    def populate_AWS_and_data_fields(self) -> None:
        if self.AWS_TOKEN is None:
            self.populate_AWS_token()
        try:
            client = boto3.client("cognito-identity", region_name=AWS_REGION)
            # IdentityId
            response = client.get_id(
                IdentityPoolId=AWS_IDENTITY_POOL_ID,
                Logins={AWS_COGNITO_ENDPOINT + "/" + AWS_USER_POOL_ID: self.AWS_TOKEN},
            )
            self.AWS_IDENTITY_ID = response["IdentityId"]
            # Credentials for Identity
            response = client.get_credentials_for_identity(
                IdentityId=self.AWS_IDENTITY_ID,
                Logins={AWS_COGNITO_ENDPOINT + "/" + AWS_USER_POOL_ID: self.AWS_TOKEN},
            )
            self.AWS_ACCESS_KEY_ID = response["Credentials"]["AccessKeyId"]
            self.AWS_SECRET_ACCESS_KEY = response["Credentials"]["SecretKey"]
            self.AWS_SESSION_TOKEN = response["Credentials"]["SessionToken"]
            if DEBUG_INFO:
                self.LOGGER.info("Pentair Cloud complete Populate AWS Fields")
            self.populate_pentair_devices()
        except Exception as err:
            self.LOGGER.error(
                "Exception while setting up Pentair Cloud (Populate AWS Fields). %s",
                err,
            )

    def get_pentair_header(self) -> str:
        return {
            "x-amz-id-token": self.AWS_TOKEN,
            "user-agent": "aws-amplify/4.3.10 react-native",
            "content-type": "application/json; charset=UTF-8",
        }

    def get_AWS_auth(self) -> AWS4Auth:
        return AWS4Auth(
            self.AWS_ACCESS_KEY_ID,
            self.AWS_SECRET_ACCESS_KEY,
            AWS_REGION,
            "execute-api",
            session_token=self.AWS_SESSION_TOKEN,
        )

    def populate_pentair_devices(self) -> None:
        if self.AWS_TOKEN is not None:
            try:
                # GetDeviceConfiguration
                endpoint = PENTAIR_ENDPOINT + PENTAIR_DEVICES_PATH
                response = requests.get(
                    endpoint,
                    auth=self.get_AWS_auth(),
                    headers=self.get_pentair_header(),
                )
                for device in response.json()["data"]:
                    if device["deviceType"] == "IF31":
                        if device["status"] == "ACTIVE":
                            self.devices.append(
                                PentairDevice(
                                    self.LOGGER,
                                    device["deviceId"],
                                    device["productInfo"]["nickName"],
                                )
                            )
                            if DEBUG_INFO:
                                self.LOGGER.info(
                                    "Found compatible device:" + device["deviceId"]
                                )
                        else:
                            if DEBUG_INFO:
                                self.LOGGER.warning(
                                    "Found inactive device:" + device["deviceId"]
                                )
                    else:
                        if DEBUG_INFO:
                            self.LOGGER.warning(
                                "Incompatible device"
                                + device["deviceType"]
                                + "/"
                                + device["pname"]
                            )
                self.update_pentair_devices_status()
            except Exception as err:
                self.LOGGER.error(
                    "Exception while setting up Pentair Cloud (Populate Pentair Device ID). %s",
                    err,
                )
        else:
            self.LOGGER.error(
                "Exception while setting up Pentair Cloud (Empty token in populate Pentair Device ID)."
            )

    def update_pentair_devices_status(self) -> None:
        if (
            self.last_update == None
            or time.time() - self.last_update > UPDATE_MIN_SECONDS
        ):
            if DEBUG_INFO:
                self.LOGGER.info("Pentair Cloud - Update Devices Status")
            self.last_update = time.time()
            self.populate_AWS_token()
            if self.AWS_TOKEN is not None:
                try:
                    devices_json_list = []
                    for device in self.devices:
                        devices_json_list.append('"' + device.pentair_device_id + '"')
                    devices_json = (
                        '{"deviceIds": [' + ",".join(devices_json_list) + "]}"
                    )
                    # devices_json = '{"deviceIds": ["' + deviceId + '"]}'
                    endpoint = PENTAIR_ENDPOINT + PENTAIR_DEVICES_2_PATH
                    response = requests.post(
                        endpoint,
                        auth=self.get_AWS_auth(),
                        headers=self.get_pentair_header(),
                        data=devices_json,
                    )
                    response_data = response.json()
                    for device_response in response_data["response"]["data"]:
                        for device in self.devices:
                            if device.pentair_device_id == device_response["deviceId"]:
                                # Check running program
                                running_program = (
                                    int(device_response["fields"]["s14"]["value"]) + 1
                                )  # Index is starting at zero
                                for i in range(
                                    1, 9
                                ):  # Technically 14 but after 10 are active but do not show on the app, I don't know why
                                    if (
                                        device_response["fields"][
                                            "zp" + str(i) + "e13"
                                        ]["value"]
                                        == "1"
                                    ):  # Program is active
                                        program_type = int(
                                            device_response["fields"][
                                                "zp" + str(i) + "e5"
                                            ]["value"]
                                        )
                                        device.update_program(
                                            i,
                                            device_response["fields"][
                                                "zp" + str(i) + "e2"
                                            ]["value"],
                                            program_type,
                                            running_program,
                                        )

                except Exception as err:
                    self.LOGGER.error(
                        "Exception while updating Pentair Cloud (update device status). %s, %s",
                        err,
                        response_data,
                    )
                    try:
                        self.LOGGER.error("Timeout detected. Logging Again")
                        if "timeout" in response_data["message"]:
                            self.authenticate(
                                self.username, self.password
                            )  # Refresh authentication in case of timeout
                    except Exception as err2:
                        self.LOGGER.error(
                            "ERROR in Timeout detection loop.",
                            err2,
                        )
            else:
                self.LOGGER.error(
                    "Exception while updating Pentair Cloud (Empty token in device status)."
                )
        else:
            if DEBUG_INFO:
                self.LOGGER.info(
                    "Pentair Cloud - Update Devices Status Requested but before min time"
                )

    def start_program(self, deviceId: str, program_id: int) -> None:
        device = None
        program = None
        for device_l in self.devices:
            if device_l.pentair_device_id == deviceId:
                device = device_l
                for program_l in device.programs:
                    if program_l.id == program_id:
                        program = program_l
        if device is None or program is None:
            self.LOGGER.error(
                "Pentair Cloud - PROGRAM/DEVICE Not Found - Start program "
                + str(program_id)
                + " on device "
                + deviceId
            )
            return
        if (
            device.last_program_start == None
            or time.time() - device.last_program_start > PROGRAM_START_MIN_SECONDS
        ):
            if DEBUG_INFO:
                self.LOGGER.info(
                    "Pentair Cloud - Start program "
                    + str(program_id)
                    + " on device "
                    + deviceId
                )
            if device.active_program is not None:  # Stop previous program
                self.stop_program(deviceId, device.active_program)
            device.last_program_start = time.time()
            self.populate_AWS_token()
            if self.AWS_TOKEN is not None:
                try:
                    endpoint = PENTAIR_ENDPOINT + PENTAIR_DEVICE_SERVICE_PATH + deviceId
                    # Enable the program
                    response = requests.put(
                        endpoint,
                        auth=self.get_AWS_auth(),
                        headers=self.get_pentair_header(),
                        data='{"payload":{"zp'
                        + str(program_id)
                        + 'e10":"'
                        + str(program.get_start_value())
                        + '"}}',
                    )
                    response_data = response.json()
                    if response_data["data"]["code"] != "set_device_success":
                        raise Exception("Wrong response code start program")
                    device.active_program = program_id
                    program.running = True
                    # Update "Last Active Program". Don't know why, but the app is doing that...
                    response = requests.put(
                        endpoint,
                        auth=self.get_AWS_auth(),
                        headers=self.get_pentair_header(),
                        data='{"payload":{"p2":"99"}}',
                    )
                except Exception as err:
                    self.LOGGER.error(
                        "Exception with Pentair API (Start Program). %s",
                        err,
                    )
            else:
                self.LOGGER.error(
                    "Exception while starting program (Empty token in device status)."
                )
        else:
            if DEBUG_INFO:
                self.LOGGER.info(
                    "Pentair Cloud - Start program Requested but before min time"
                )

    def stop_program(self, deviceId: str, program_id: int) -> None:
        device = None
        program = None
        for device_l in self.devices:
            if device_l.pentair_device_id == deviceId:
                device = device_l
                for program_l in device.programs:
                    if program_l.id == program_id:
                        program = program_l
        if device is None or program is None:
            self.LOGGER.error(
                "Pentair Cloud - PROGRAM/DEVICE Not Found - Stop program "
                + str(program_id)
                + " on device "
                + deviceId
            )
            return
        if DEBUG_INFO:
            self.LOGGER.info(
                "Pentair Cloud - Stop program "
                + str(program_id)
                + " on device "
                + deviceId
            )
        self.populate_AWS_token()
        if self.AWS_TOKEN is not None:
            try:
                endpoint = PENTAIR_ENDPOINT + PENTAIR_DEVICE_SERVICE_PATH + deviceId
                # Enable the program
                response = requests.put(
                    endpoint,
                    auth=self.get_AWS_auth(),
                    headers=self.get_pentair_header(),
                    data='{"payload":{"zp'
                    + str(program_id)
                    + 'e10":"'
                    + str(program.get_stop_value())
                    + '"}}',
                )
                response_data = response.json()
                if response_data["data"]["code"] != "set_device_success":
                    raise Exception("Wrong response code stop program")
                device.active_program = None
                program.running = False
                # Update "Last Active Program"
                response = requests.put(
                    endpoint,
                    auth=self.get_AWS_auth(),
                    headers=self.get_pentair_header(),
                    data='{"payload":{"p2":"' + str(program_id - 1) + '"}}',
                )
            except Exception as err:
                self.LOGGER.error(
                    "Exception with Pentair API (Stop Program). %s",
                    err,
                )
        else:
            self.LOGGER.error(
                "Exception while stopping program (Empty token in device status)."
            )

    def authenticate(self, username: str, password: str) -> bool:
        try:
            # u = await self.hass.async_add_executor_job(
            u = self.get_cognito_client(username)
            u.authenticate(password)
            self.cognito_client = u
            self.cognito_client.get_user()
            self.username = username
            self.password = password
            return True

        except Exception as err:
            self.LOGGER.error("Exception while logging with Pentair Cloud. %s", err)
            return False
