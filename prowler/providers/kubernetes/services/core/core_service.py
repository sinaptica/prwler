import socket
from typing import List, Optional

from pydantic.v1 import BaseModel

from kubernetes import client
from prowler.lib.logger import logger
from prowler.providers.kubernetes.kubernetes_provider import KubernetesProvider
from prowler.providers.kubernetes.lib.service.service import KubernetesService


class Core(KubernetesService):
    def __init__(self, provider: KubernetesProvider):
        super().__init__(provider)
        self.client = client.CoreV1Api(self.api_client)
        self.namespaces = provider.namespaces
        self.pods = {}
        self._get_pods()
        self.config_maps = {}
        self._list_config_maps()
        self.nodes = {}
        self._list_nodes()
        self._in_worker_node()

    def _get_pods(self):
        try:
            for namespace in self.namespaces:
                pods = self.client.list_namespaced_pod(namespace)
                for pod in pods.items:
                    pod_containers = {}
                    containers = pod.spec.containers if pod.spec.containers else []
                    init_containers = (
                        pod.spec.init_containers if pod.spec.init_containers else []
                    )
                    ephemeral_containers = (
                        pod.spec.ephemeral_containers
                        if pod.spec.ephemeral_containers
                        else []
                    )
                    for container in (
                        containers + init_containers + ephemeral_containers
                    ):
                        pod_containers[container.name] = Container(
                            name=container.name,
                            image=container.image,
                            command=container.command if container.command else None,
                            ports=(
                                [
                                    {"containerPort": port.container_port}
                                    for port in container.ports
                                ]
                                if container.ports
                                else None
                            ),
                            env=(
                                [
                                    {"name": env.name, "value": env.value}
                                    for env in container.env
                                ]
                                if container.env
                                else None
                            ),
                            security_context=(
                                container.security_context.to_dict()
                                if container.security_context
                                else {}
                            ),
                        )
                    self.pods[pod.metadata.uid] = Pod(
                        name=pod.metadata.name,
                        uid=pod.metadata.uid,
                        namespace=pod.metadata.namespace,
                        labels=pod.metadata.labels,
                        annotations=pod.metadata.annotations,
                        node_name=pod.spec.node_name,
                        service_account=pod.spec.service_account_name,
                        status_phase=pod.status.phase,
                        pod_ip=pod.status.pod_ip,
                        host_ip=pod.status.host_ip,
                        host_pid=pod.spec.host_pid,
                        host_ipc=pod.spec.host_ipc,
                        host_network=pod.spec.host_network,
                        security_context=(
                            pod.spec.security_context.to_dict()
                            if pod.spec.security_context
                            else {}
                        ),
                        containers=pod_containers,
                    )
        except Exception as error:
            logger.error(
                f"{error.__class__.__name__}[{error.__traceback__.tb_lineno}]: {error}"
            )

    def _list_config_maps(self):
        try:
            response = self.client.list_config_map_for_all_namespaces()
            for cm in response.items:
                self.config_maps[cm.metadata.uid] = ConfigMap(
                    name=cm.metadata.name,
                    namespace=cm.metadata.namespace,
                    uid=cm.metadata.uid,
                    data=cm.data,
                    labels=cm.metadata.labels,
                    annotations=cm.metadata.annotations,
                )
        except Exception as error:
            logger.error(
                f"{error.__class__.__name__}[{error.__traceback__.tb_lineno}]: {error}"
            )

    def _list_nodes(self):
        try:
            response = self.client.list_node()
            for node in response.items:
                node_model = Node(
                    name=node.metadata.name,
                    uid=node.metadata.uid,
                    namespace=(
                        node.metadata.namespace
                        if node.metadata.namespace
                        else "cluster-wide"
                    ),
                    labels=node.metadata.labels,
                    annotations=node.metadata.annotations,
                    unschedulable=node.spec.unschedulable,
                    node_info=(
                        node.status.node_info.to_dict()
                        if node.status.node_info
                        else None
                    ),
                )
                self.nodes[node.metadata.uid] = node_model
        except Exception as error:
            logger.error(
                f"{error.__class__.__name__}[{error.__traceback__.tb_lineno}]: {error}"
            )

    def _in_worker_node(self):
        try:
            hostname = socket.gethostname()
            for node in self.nodes.values():
                if hostname == node.name:
                    node.inside = True

        except Exception as error:
            logger.error(
                f"{error.__class__.__name__}[{error.__traceback__.tb_lineno}]: {error}"
            )


class Container(BaseModel):
    name: str
    image: str
    command: Optional[List[str]]
    ports: Optional[List[dict]]
    env: Optional[List[dict]]
    security_context: dict


class Pod(BaseModel):
    name: str
    uid: str
    namespace: str
    labels: Optional[dict]
    annotations: Optional[dict]
    node_name: Optional[str]
    service_account: Optional[str]
    status_phase: Optional[str]
    pod_ip: Optional[str]
    host_ip: Optional[str]
    host_pid: Optional[str]
    host_ipc: Optional[str]
    host_network: Optional[bool]
    security_context: Optional[dict]
    containers: Optional[dict]


class ConfigMap(BaseModel):
    name: str
    namespace: str
    uid: str
    data: Optional[dict]
    labels: Optional[dict]
    kubelet_args: list = []
    annotations: Optional[dict]


class Node(BaseModel):
    name: str
    uid: str
    namespace: str
    labels: Optional[dict]
    annotations: Optional[dict]
    unschedulable: Optional[bool]
    node_info: Optional[dict]
    inside: bool = False
