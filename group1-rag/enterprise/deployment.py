"""
Kubernetes Deployment Manifest Generator for Group One Trading RAG
- Auto-generates K8s manifests for:
  * Deployments (API, workers)
  * Services (ClusterIP, LoadBalancer)
  * StatefulSets (Postgres, Redis)
  * ConfigMaps (config files)
  * Secrets (sensitive data)
  * PersistentVolumes/Claims
  * HorizontalPodAutoscaler
  * NetworkPolicies
  * ServiceMonitor (Prometheus)
"""

import json
import yaml
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict

# ============================================================================
# K8S RESOURCE BUILDERS
# ============================================================================

@dataclass
class ResourceConfig:
    """Base configuration for K8s resources."""
    name: str
    namespace: str = "default"
    labels: Dict[str, str] = None

    def __post_init__(self):
        if self.labels is None:
            self.labels = {
                "app": self.name,
                "version": "4.0.0",
                "component": "rag",
            }

class ManifestGenerator:
    """Generate Kubernetes manifests in YAML format."""

    @staticmethod
    def generate_namespace(name: str) -> Dict[str, Any]:
        """Generate Namespace resource."""
        return {
            "apiVersion": "v1",
            "kind": "Namespace",
            "metadata": {
                "name": name,
                "labels": {"name": name},
            }
        }

    @staticmethod
    def generate_configmap(
        name: str,
        namespace: str,
        data: Dict[str, str],
        labels: Dict[str, str] = None,
    ) -> Dict[str, Any]:
        """Generate ConfigMap resource."""
        return {
            "apiVersion": "v1",
            "kind": "ConfigMap",
            "metadata": {
                "name": name,
                "namespace": namespace,
                "labels": labels or {"app": name},
            },
            "data": data,
        }

    @staticmethod
    def generate_secret(
        name: str,
        namespace: str,
        data: Dict[str, str],
        labels: Dict[str, str] = None,
    ) -> Dict[str, Any]:
        """Generate Secret resource."""
        import base64
        encoded_data = {
            k: base64.b64encode(v.encode()).decode()
            for k, v in data.items()
        }
        return {
            "apiVersion": "v1",
            "kind": "Secret",
            "metadata": {
                "name": name,
                "namespace": namespace,
                "labels": labels or {"app": name},
            },
            "type": "Opaque",
            "data": encoded_data,
        }

    @staticmethod
    def generate_deployment(
        name: str,
        namespace: str,
        image: str,
        replicas: int = 2,
        port: int = 8000,
        env_vars: Dict[str, str] = None,
        resources: Dict[str, Any] = None,
        labels: Dict[str, str] = None,
    ) -> Dict[str, Any]:
        """Generate Deployment resource."""
        if labels is None:
            labels = {"app": name}

        if resources is None:
            resources = {
                "requests": {"cpu": "100m", "memory": "256Mi"},
                "limits": {"cpu": "1", "memory": "1Gi"},
            }

        if env_vars is None:
            env_vars = {}

        env = [{"name": k, "value": v} for k, v in env_vars.items()]

        return {
            "apiVersion": "apps/v1",
            "kind": "Deployment",
            "metadata": {
                "name": name,
                "namespace": namespace,
                "labels": labels,
            },
            "spec": {
                "replicas": replicas,
                "selector": {"matchLabels": {"app": name}},
                "template": {
                    "metadata": {"labels": labels},
                    "spec": {
                        "containers": [
                            {
                                "name": name,
                                "image": image,
                                "ports": [{"containerPort": port}],
                                "env": env,
                                "resources": resources,
                                "livenessProbe": {
                                    "httpGet": {
                                        "path": "/health",
                                        "port": port,
                                    },
                                    "initialDelaySeconds": 30,
                                    "periodSeconds": 10,
                                },
                                "readinessProbe": {
                                    "httpGet": {
                                        "path": "/ready",
                                        "port": port,
                                    },
                                    "initialDelaySeconds": 5,
                                    "periodSeconds": 5,
                                },
                            }
                        ],
                        "restartPolicy": "Always",
                    },
                },
            },
        }

    @staticmethod
    def generate_service(
        name: str,
        namespace: str,
        app_label: str,
        port: int = 8000,
        target_port: int = 8000,
        service_type: str = "ClusterIP",
        labels: Dict[str, str] = None,
    ) -> Dict[str, Any]:
        """Generate Service resource."""
        return {
            "apiVersion": "v1",
            "kind": "Service",
            "metadata": {
                "name": name,
                "namespace": namespace,
                "labels": labels or {"app": name},
            },
            "spec": {
                "type": service_type,
                "selector": {"app": app_label},
                "ports": [
                    {
                        "port": port,
                        "targetPort": target_port,
                        "protocol": "TCP",
                    }
                ],
            },
        }

    @staticmethod
    def generate_statefulset(
        name: str,
        namespace: str,
        image: str,
        replicas: int = 3,
        port: int = 5432,
        storage_class: str = "standard",
        storage_size: str = "10Gi",
        labels: Dict[str, str] = None,
    ) -> Dict[str, Any]:
        """Generate StatefulSet resource for stateful services."""
        if labels is None:
            labels = {"app": name}

        return {
            "apiVersion": "apps/v1",
            "kind": "StatefulSet",
            "metadata": {
                "name": name,
                "namespace": namespace,
                "labels": labels,
            },
            "spec": {
                "serviceName": f"{name}-headless",
                "replicas": replicas,
                "selector": {"matchLabels": {"app": name}},
                "template": {
                    "metadata": {"labels": labels},
                    "spec": {
                        "containers": [
                            {
                                "name": name,
                                "image": image,
                                "ports": [{"containerPort": port}],
                                "volumeMounts": [
                                    {
                                        "name": "data",
                                        "mountPath": "/data",
                                    }
                                ],
                            }
                        ],
                    },
                },
                "volumeClaimTemplates": [
                    {
                        "metadata": {"name": "data"},
                        "spec": {
                            "accessModes": ["ReadWriteOnce"],
                            "storageClassName": storage_class,
                            "resources": {"requests": {"storage": storage_size}},
                        },
                    }
                ],
            },
        }

    @staticmethod
    def generate_hpa(
        name: str,
        namespace: str,
        target_deployment: str,
        min_replicas: int = 2,
        max_replicas: int = 10,
        cpu_threshold: int = 70,
        memory_threshold: int = 80,
    ) -> Dict[str, Any]:
        """Generate HorizontalPodAutoscaler resource."""
        return {
            "apiVersion": "autoscaling/v2",
            "kind": "HorizontalPodAutoscaler",
            "metadata": {
                "name": name,
                "namespace": namespace,
            },
            "spec": {
                "scaleTargetRef": {
                    "apiVersion": "apps/v1",
                    "kind": "Deployment",
                    "name": target_deployment,
                },
                "minReplicas": min_replicas,
                "maxReplicas": max_replicas,
                "metrics": [
                    {
                        "type": "Resource",
                        "resource": {
                            "name": "cpu",
                            "target": {
                                "type": "Utilization",
                                "averageUtilization": cpu_threshold,
                            },
                        },
                    },
                    {
                        "type": "Resource",
                        "resource": {
                            "name": "memory",
                            "target": {
                                "type": "Utilization",
                                "averageUtilization": memory_threshold,
                            },
                        },
                    },
                ],
            },
        }

    @staticmethod
    def generate_networkpolicy(
        name: str,
        namespace: str,
        app_label: str,
    ) -> Dict[str, Any]:
        """Generate NetworkPolicy for security."""
        return {
            "apiVersion": "networking.k8s.io/v1",
            "kind": "NetworkPolicy",
            "metadata": {
                "name": name,
                "namespace": namespace,
            },
            "spec": {
                "podSelector": {"matchLabels": {"app": app_label}},
                "policyTypes": ["Ingress", "Egress"],
                "ingress": [
                    {
                        "from": [
                            {
                                "podSelector": {
                                    "matchLabels": {"app": "nginx-ingress"}
                                }
                            }
                        ]
                    }
                ],
                "egress": [
                    {
                        "to": [
                            {
                                "podSelector": {
                                    "matchLabels": {"app": "postgres"}
                                }
                            }
                        ]
                    },
                    {
                        "to": [
                            {
                                "podSelector": {
                                    "matchLabels": {"app": "redis"}
                                }
                            }
                        ]
                    },
                ],
            },
        }

    @staticmethod
    def generate_servicemonitor(
        name: str,
        namespace: str,
        app_label: str,
        port: str = "metrics",
        interval: str = "30s",
    ) -> Dict[str, Any]:
        """Generate ServiceMonitor for Prometheus scraping."""
        return {
            "apiVersion": "monitoring.coreos.com/v1",
            "kind": "ServiceMonitor",
            "metadata": {
                "name": name,
                "namespace": namespace,
            },
            "spec": {
                "selector": {"matchLabels": {"app": app_label}},
                "endpoints": [
                    {
                        "port": port,
                        "interval": interval,
                    }
                ],
            },
        }

    @staticmethod
    def generate_persistentvolume(
        name: str,
        size: str = "10Gi",
        storage_class: str = "standard",
        access_modes: List[str] = None,
    ) -> Dict[str, Any]:
        """Generate PersistentVolume resource."""
        if access_modes is None:
            access_modes = ["ReadWriteOnce"]

        return {
            "apiVersion": "v1",
            "kind": "PersistentVolume",
            "metadata": {"name": name},
            "spec": {
                "capacity": {"storage": size},
                "accessModes": access_modes,
                "storageClassName": storage_class,
                "hostPath": {"path": f"/mnt/data/{name}"},
            },
        }

# ============================================================================
# COMPLETE DEPLOYMENT MANIFEST
# ============================================================================

class KubernetesDeployment:
    """Generate complete K8s deployment for Group One RAG."""

    def __init__(self, namespace: str = "group1-rag"):
        self.namespace = namespace
        self.gen = ManifestGenerator()

    def generate_all_manifests(
        self,
        image_tag: str = "latest",
        api_replicas: int = 3,
        worker_replicas: int = 2,
    ) -> List[Dict[str, Any]]:
        """Generate all K8s manifests."""
        manifests = []

        # 1. Namespace
        manifests.append(self.gen.generate_namespace(self.namespace))

        # 2. ConfigMap for app config
        manifests.append(self.gen.generate_configmap(
            name="rag-config",
            namespace=self.namespace,
            data={
                "LOG_LEVEL": "INFO",
                "ENVIRONMENT": "production",
                "WORKERS": "4",
            }
        ))

        # 3. Secrets (in production, use vault)
        manifests.append(self.gen.generate_secret(
            name="rag-secrets",
            namespace=self.namespace,
            data={
                "SECRET_KEY": "change-me-in-production",
                "DB_PASSWORD": "change-me-in-production",
            }
        ))

        # 4. PersistentVolumes
        manifests.append(self.gen.generate_persistentvolume(
            name="postgres-pv",
            size="20Gi",
        ))
        manifests.append(self.gen.generate_persistentvolume(
            name="redis-pv",
            size="10Gi",
        ))

        # 5. Postgres StatefulSet
        manifests.append(self.gen.generate_statefulset(
            name="postgres",
            namespace=self.namespace,
            image="postgres:15-alpine",
            replicas=1,
            port=5432,
            storage_size="20Gi",
        ))
        manifests.append(self.gen.generate_service(
            name="postgres",
            namespace=self.namespace,
            app_label="postgres",
            port=5432,
            service_type="ClusterIP",
        ))

        # 6. Redis StatefulSet
        manifests.append(self.gen.generate_statefulset(
            name="redis",
            namespace=self.namespace,
            image="redis:7-alpine",
            replicas=1,
            port=6379,
            storage_size="10Gi",
        ))
        manifests.append(self.gen.generate_service(
            name="redis",
            namespace=self.namespace,
            app_label="redis",
            port=6379,
            service_type="ClusterIP",
        ))

        # 7. API Deployment
        api_image = f"group1-rag-api:{image_tag}"
        manifests.append(self.gen.generate_deployment(
            name="rag-api",
            namespace=self.namespace,
            image=api_image,
            replicas=api_replicas,
            port=8000,
            env_vars={
                "DATABASE_URL": "postgresql://postgres:${DB_PASSWORD}@postgres:5432/group1_rag",
                "REDIS_URL": "redis://redis:6379/0",
                "LOG_LEVEL": "INFO",
                "ENVIRONMENT": "production",
            },
        ))

        # 8. API Service (LoadBalancer for external access)
        manifests.append(self.gen.generate_service(
            name="rag-api",
            namespace=self.namespace,
            app_label="rag-api",
            port=80,
            target_port=8000,
            service_type="LoadBalancer",
        ))

        # 9. Worker Deployment
        manifests.append(self.gen.generate_deployment(
            name="rag-worker",
            namespace=self.namespace,
            image=api_image,
            replicas=worker_replicas,
            env_vars={
                "DATABASE_URL": "postgresql://postgres:${DB_PASSWORD}@postgres:5432/group1_rag",
                "REDIS_URL": "redis://redis:6379/0",
                "WORKER_TYPE": "background",
            },
        ))

        # 10. HPA for API
        manifests.append(self.gen.generate_hpa(
            name="rag-api-hpa",
            namespace=self.namespace,
            target_deployment="rag-api",
            min_replicas=2,
            max_replicas=10,
            cpu_threshold=70,
        ))

        # 11. HPA for Workers
        manifests.append(self.gen.generate_hpa(
            name="rag-worker-hpa",
            namespace=self.namespace,
            target_deployment="rag-worker",
            min_replicas=1,
            max_replicas=5,
            cpu_threshold=80,
        ))

        # 12. NetworkPolicy
        manifests.append(self.gen.generate_networkpolicy(
            name="rag-network-policy",
            namespace=self.namespace,
            app_label="rag-api",
        ))

        # 13. ServiceMonitor for Prometheus
        manifests.append(self.gen.generate_servicemonitor(
            name="rag-api-monitor",
            namespace=self.namespace,
            app_label="rag-api",
        ))

        return manifests

    def export_yaml(self, manifests: List[Dict[str, Any]], output_file: str):
        """Export manifests to YAML file."""
        with open(output_file, "w") as f:
            for i, manifest in enumerate(manifests):
                if i > 0:
                    f.write("---\n")
                yaml.dump(manifest, f, default_flow_style=False)

    def export_json(self, manifests: List[Dict[str, Any]], output_file: str):
        """Export manifests to JSON file."""
        with open(output_file, "w") as f:
            json.dump(manifests, f, indent=2)

# ============================================================================
# USAGE
# ============================================================================

if __name__ == "__main__":
    deployer = KubernetesDeployment(namespace="group1-rag-prod")

    # Generate manifests
    manifests = deployer.generate_all_manifests(
        image_tag="v4.0.0",
        api_replicas=3,
        worker_replicas=2,
    )

    # Export to YAML
    deployer.export_yaml(manifests, "/tmp/k8s-manifests.yaml")
    print(f"Generated {len(manifests)} K8s manifests -> /tmp/k8s-manifests.yaml")

    # Can deploy with: kubectl apply -f /tmp/k8s-manifests.yaml
