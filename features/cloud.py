import os
import logging
import pycloudlib  # type: ignore
import time
import yaml

try:
    from typing import Tuple, List, Optional  # noqa
except ImportError:
    # typing isn't available on trusty, so ignore its absence
    pass


class Cloud:
    """Base class for cloud providers that should be tested through behave.

    :param tag:
        A tag to be used when creating the resources on the cloud provider
    :region:
        The region to create the cloud resources on
    :machine_type:
        A string representing the type of machine to launch (pro or generic)
    """

    name = ""
    pro_ids_path = ""
    env_vars: "Tuple[str, ...]" = ()

    def __init__(
        self,
        machine_type: str,
        region: "Optional[str]" = None,
        tag: "Optional[str]" = "uaclientci",
    ) -> None:
        self.tag = tag
        self.machine_type = machine_type
        self.region = region
        self._api = None

        missing_env_vars = self.missing_env_vars()
        if missing_env_vars:
            logging.warning(
                "".join(
                    [
                        "UACLIENT_BEHAVE_MACHINE_TYPE=pro.{} requires".format(
                            self.name
                        ),
                        " the following env vars:\n",
                        *self.format_missing_env_vars(missing_env_vars),
                    ]
                )
            )

    @property
    def api(self) -> pycloudlib.cloud.BaseCloud:
        """Return the api used to interact with the cloud provider."""
        raise NotImplementedError

    def manage_ssh_key(self, private_key_path: "Optional[str]" = None) -> None:
        """Create and manage ssh key pairs to be used in the cloud provider.

        :param private_key_path:
            Location of the private key path to use. If None, the location
            will be a default location.
        """
        raise NotImplementedError

    def _create_instance(
        self,
        series: str,
        image_name: "Optional[str]" = None,
        user_data: "Optional[str]" = None,
    ) -> pycloudlib.instance:
        """Create an instance for on the cloud provider.

        :param series:
            The ubuntu release to be used when creating an instance. We will
            create an image based on this value if the used does not provide
            a image_name value
        :param image_name:
            The name of the image to be used when creating the instance
        :param user_data:
            The user data to be passed when creating the instance

        :returns:
            A cloud provider instance
        """
        raise NotImplementedError

    def launch(
        self,
        series: str,
        image_name: "Optional[str]" = None,
        user_data: "Optional[str]" = None,
    ) -> pycloudlib.instance.BaseInstance:
        """Create and wait for cloud provider instance to be ready.

        :param series:
            The ubuntu release to be used when creating an instance. We will
            create an image based on this value if the used does not provide
            a image_name value
        :param image_name:
            The name of the image to be used when creating the instance
        :param user_data:
            The user data to be passed when creating the instance

        :returns:
            An cloud provider instance
        """
        inst = self._create_instance(series, image_name, user_data)
        print(
            "--- {} PRO instance launched: {}. Waiting for ssh access".format(
                self.name, inst.id
            )
        )
        time.sleep(15)
        for sleep in (5, 10, 15):
            try:
                inst.wait()
                break
            except Exception as e:
                print("--- Retrying instance.wait on {}".format(str(e)))

        return inst

    def get_instance_id(
        self, instance: pycloudlib.instance.BaseInstance
    ) -> str:
        """Return the instance identifier.

        :param instance:
            An instance created on the cloud provider

        :returns:
            The string of the unique instance id
        """
        return instance.id

    def format_missing_env_vars(self, missing_env_vars: "List") -> "List[str]":
        """Format missing env vars to be displayed in log.

        :returns:
            A list of env string formatted to be used when logging
        """
        return [" - {}\n".format(env_var) for env_var in missing_env_vars]

    def missing_env_vars(self) -> "List[str]":
        """Return a list of env variables necessary for this cloud provider.

        :returns:
            A list of string representing the missing variables
        """
        return [
            env_name
            for env_name in self.env_vars
            if not getattr(
                self, env_name.lower().replace("uaclient_behave_", "")
            )
        ]

    def locate_image_name(self, series: str) -> str:
        """Locate and return the image name to use for vm provision.

        :param series:
            The ubuntu release to be used when locating the image name

        :returns:
            A image name to use when provisioning a virtual machine
            based on the series value
        """
        if not series:
            raise ValueError(
                "Must provide either series or image_name to launch azure"
            )

        if "pro" in self.machine_type:
            with open(self.pro_ids_path, "r") as stream:
                pro_ids = yaml.safe_load(stream.read())
            image_name = pro_ids[series]
        else:
            image_name = self.api.daily_image(release=series)

        return image_name


class EC2(Cloud):
    """Class that represents the EC2 cloud provider.

    :param aws_access_key_id:
        The aws access key id
    :param aws_secret_access_key:
        The aws secret access key
    :region:
        The region to be used to create the aws instances
    :machine_type:
        A string representing the type of machine to launch (pro or generic)
    :tag:
        A tag to be used when creating the resources on the cloud provider
    """

    EC2_KEY_FILE = "uaclient.pem"
    name = "aws"
    env_vars: "Tuple[str, ...]" = (
        "aws_access_key_id",
        "aws_secret_access_key",
    )
    pro_ids_path = "features/aws-ids.yaml"

    def __init__(
        self,
        aws_access_key_id: "Optional[str]",
        aws_secret_access_key: "Optional[str]",
        machine_type: str,
        region: "Optional[str]" = "us-east-2",
        tag: "Optional[str]" = None,
    ) -> None:
        self.aws_access_key_id = aws_access_key_id
        self.aws_secret_access_key = aws_secret_access_key
        logging.basicConfig(
            filename="pycloudlib-behave.log", level=logging.DEBUG
        )

        super().__init__(region=region, machine_type=machine_type, tag=tag)

    @property
    def api(self) -> pycloudlib.cloud.BaseCloud:
        """Return the api used to interact with the cloud provider."""
        if self._api is None:
            self._api = pycloudlib.EC2(
                tag=self.tag,
                access_key_id=self.aws_access_key_id,
                secret_access_key=self.aws_secret_access_key,
                region=self.region,
            )

        return self._api

    def manage_ssh_key(self, private_key_path: "Optional[str]" = None) -> None:
        """Create and manage ssh key pairs to be used in the cloud provider.

        :param private_key_path:
            Location of the private key path to use. If None, the location
            will be a default location.
        """
        if not private_key_path:
            private_key_path = self.EC2_KEY_FILE

        if not os.path.exists(private_key_path):
            if "uaclient-integration" in self.api.list_keys():
                self.api.delete_key("uaclient-integration")
            keypair = self.api.client.create_key_pair(
                KeyName="uaclient-integration"
            )

            with open(private_key_path, "w") as stream:
                stream.write(keypair["KeyMaterial"])
            os.chmod(private_key_path, 0o600)

        self.api.use_key(
            private_key_path, private_key_path, "uaclient-integration"
        )

    def _create_instance(
        self,
        series: str,
        image_name: "Optional[str]" = None,
        user_data: "Optional[str]" = None,
    ) -> pycloudlib.instance:
        """Launch an instance on the cloud provider.

        :param series:
            The ubuntu release to be used when creating an instance. We will
            create an image based on this value if the used does not provide
            a image_name value
        :param image_name:
            The name of the image to be used when creating the instance
        :param user_data:
            The user data to be passed when creating the instance

        :returns:
            An AWS cloud provider instance
        """
        if not image_name:
            image_name = self.locate_image_name(series)

        print("--- Launching AWS PRO image {}({})".format(image_name, series))
        vpc = self.api.get_or_create_vpc(name="uaclient-integration")

        try:
            inst = self.api.launch(image_name, user_data=user_data, vpc=vpc)
        except Exception as e:
            print(str(e))
            raise

        return inst


class Azure(Cloud):
    """Class that represents the Azure cloud provider.

    :param az_client_id:
        The Azure client id
    :param az_client_secret
        The Azure client secret
    :param az_tenant_id:
        The Azure tenant id
    :param az_subscription_id:
        The Azure subscription id
    :machine_type:
        A string representing the type of machine to launch (pro or generic)
    :tag:
        A tag to be used when creating the resources on the cloud provider
    :region:
        The region to create the resources on
    :keep_resources:
        A boolean that indicates if we should keep the resources after
        running the test
    """

    AZURE_PUB_KEY_FILE = "ua_az_pub_key.txt"
    AZURE_PRIV_KEY_FILE = "ua_az_priv_key.txt"
    name = "Azure"
    env_vars: "Tuple[str, ...]" = (
        "az_client_id",
        "az_client_secret",
        "az_tenant_id",
        "az_subscription_id",
    )
    pro_ids_path = "features/azure-ids.yaml"

    def __init__(
        self,
        machine_type: str,
        region: "Optional[str]" = "centralus",
        tag: "Optional[str]" = None,
        az_client_id: "Optional[str]" = None,
        az_client_secret: "Optional[str]" = None,
        az_tenant_id: "Optional[str]" = None,
        az_subscription_id: "Optional[str]" = None,
        keep_resources: bool = False,
    ) -> None:
        self.az_client_id = az_client_id
        self.az_client_secret = az_client_secret
        self.az_tenant_id = az_tenant_id
        self.az_subscription_id = az_subscription_id
        self.keep_resources = keep_resources

        super().__init__(machine_type=machine_type, region=region, tag=tag)

    @property
    def api(self) -> pycloudlib.cloud.BaseCloud:
        """Return the api used to interact with the cloud provider."""
        if self._api is None:
            self._api = pycloudlib.Azure(
                tag=self.tag,
                client_id=self.az_client_id,
                client_secret=self.az_client_secret,
                tenant_id=self.az_tenant_id,
                subscription_id=self.az_subscription_id,
            )

        return self._api

    def get_instance_id(
        self, instance: pycloudlib.instance.BaseInstance
    ) -> str:
        """Return the instance identifier.

        :param instance:
            An instance created on the cloud provider

        :returns:
            The string of the unique instance id
        """
        # For Azure, the API identifier uses the instance name
        # instead of the instance id
        return instance.name

    def manage_ssh_key(self, private_key_path: "Optional[str]" = None) -> None:
        """Create and manage ssh key pairs to be used in the cloud provider.

        :param private_key_path:
            Location of the private key path to use. If None, the location
            will be a default location.
        """
        if not os.path.exists(self.AZURE_PUB_KEY_FILE):
            if "uaclient-integration" in self.api.list_keys():
                self.api.delete_key("uaclient-integration")
            pub_key, priv_key = self.api.create_key_pair(
                key_name="uaclient-integration"
            )

            with open(self.AZURE_PUB_KEY_FILE, "w") as stream:
                stream.write(pub_key)

            with open(self.AZURE_PRIV_KEY_FILE, "w") as stream:
                stream.write(priv_key)

            os.chmod(self.AZURE_PUB_KEY_FILE, 0o600)
            os.chmod(self.AZURE_PRIV_KEY_FILE, 0o600)

        self.api.use_key(
            self.AZURE_PUB_KEY_FILE,
            self.AZURE_PRIV_KEY_FILE,
            "uaclient-integration",
        )

    def _create_instance(
        self,
        series: str,
        image_name: "Optional[str]" = None,
        user_data: "Optional[str]" = None,
    ) -> pycloudlib.instance:
        """Launch an instance on the cloud provider.

        :param series:
            The ubuntu release to be used when creating an instance. We will
            create an image based on this value if the used does not provide
            a image_name value
        :param image_name:
            The name of the image to be used when creating the instance
        :param user_data:
            The user data to be passed when creating the instance

        :returns:
            An AWS cloud provider instance
        """
        if not image_name:
            image_name = self.locate_image_name(series)

        print(
            "--- Launching Azure PRO image {}({})".format(image_name, series)
        )
        inst = self.api.launch(image_id=image_name, user_data=user_data)
        return inst
