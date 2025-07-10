from app.helpers.alias import create_alias
from flask import current_app
from types import SimpleNamespace
from kubernetes import client
import base64
import json
from app.helpers.clean_up import resource_clean_up
from app.helpers.crane_app_logger import logger
from flask import current_app

# Constants for better maintainability
DEFAULT_DOCKER_SERVER = 'docker.io'
DEFAULT_REPLICAS = 1
DEFAULT_APP_PORT = 80
DEFAULT_STORAGE = '1Gi'
DEFAULT_MOUNT_PATH = '/data'
DEFAULT_SERVICE_APPEND = "default"
DEFAULT_PORT = 8000
HUGGINGFACE_PORT = 9000
JUPYTER_MOUNT_PATH = '/home/jovyan/work'
DEFAULT_NAMESPACE_APP_NAME = 'cranecloud-app'

# Resource limits and requests
DEFAULT_RESOURCE_LIMITS = {
    "memory": "2Gi",
    "cpu": "1"
}
DEFAULT_RESOURCE_REQUESTS = {
    "memory": "1Gi",
    "cpu": "500m"
}

# GPU resource limits for AI models
GPU_RESOURCE_LIMITS = {
    "memory": "8Gi",
    "cpu": "4"
}
GPU_RESOURCE_REQUESTS = {
    "memory": "2Gi",
    "cpu": "2"
}


def get_app_subdomain(alias, domain):
    """Generate application subdomain from alias and domain."""
    return f'{alias}.{domain}'


def create_kube_clients(kube_host, kube_token):
    """
    Create and configure Kubernetes API clients.

    Args:
        kube_host (str): Kubernetes API server host
        kube_token (str): Kubernetes authentication token

    Returns:
        SimpleNamespace: Object containing configured Kubernetes API clients
    """
    # Configure client
    config = client.Configuration()
    config.host = kube_host
    config.api_key['authorization'] = kube_token
    config.api_key_prefix['authorization'] = 'Bearer'
    config.verify_ssl = False

    # Create API instances
    api_client = client.ApiClient()
    kube = client.CoreV1Api(client.ApiClient(config))
    appsv1_api = client.AppsV1Api(client.ApiClient(config))
    batchv1_api = client.BatchV1Api(client.ApiClient(config))
    storageV1Api = client.StorageV1Api(client.ApiClient(config))
    networking_api = client.NetworkingV1Api(client.ApiClient(config))
    custom_api = client.CustomObjectsApi(client.ApiClient(config))

    return SimpleNamespace(
        kube=kube,
        networking_api=networking_api,
        appsv1_api=appsv1_api,
        api_client=api_client,
        batchv1_api=batchv1_api,
        storageV1Api=storageV1Api,
        custom_api=custom_api
    )


def _initialize_resource_registry():
    """Initialize resource registry for tracking created Kubernetes resources."""
    return {
        'db_deployment': False,
        'db_service': False,
        'image_pull_secret': False,
        'app_deployment': False,
        'app_service': False,
        'ingress_entry': False,
        'seldon_deployment': False,
        'pvc': False
    }


def _setup_notebook_data(app_data, app_name):
    """Setup notebook-specific configuration data."""
    return {
        'image': 'cranecloud/jupyter-notebook:latest',
        'port': 8888,
        'is_ai': True,
        'is_notebook': True,
        'name': app_name
    }


def _setup_modal_data(app_data, app_name):
    """Setup modal-specific configuration data."""
    model_server = app_data.get('model_server', 'MLFLOW_SERVER')
    port = HUGGINGFACE_PORT if model_server == 'HUGGINGFACE_SERVER' else DEFAULT_PORT

    return {
        'model_image_uri': app_data.get('model_image_uri'),
        'port': port,
        'is_ai': True,
        'is_modal': True,
        'api_type': app_data.get('api_type', 'REST'),
        'model_server': model_server,
        'name': app_name
    }


def _extract_app_data(app_data, app=None):
    """Extract and validate application data from input parameters."""
    is_notebook = app_data.get('is_notebook', False)
    is_modal = app_data.get('is_modal', False)
    app_name = app_data.get('name', None)
    model_server = app_data.get('model_server', 'MLFLOW_SERVER')

    # Validate required fields for notebook/modal apps
    if (is_notebook or is_modal) and not app_name:
        return SimpleNamespace(
            message='Missing data for required field, name',
            status_code=400
        )

    # Setup notebook or modal specific data
    if is_notebook:
        app_data.update(_setup_notebook_data(app_data, app_name))
    if is_modal:
        app_data.update(_setup_modal_data(app_data, app_name))

    # Extract common app parameters
    app_image = app_data.get('image', None)
    docker_server = app_data.get('docker_server', DEFAULT_DOCKER_SERVER)
    docker_password = app_data.get('docker_password', None)
    app_alias = create_alias(app_name)
    command_string = app_data.get('command', None)
    env_vars = app_data.get('env_vars', None)
    private_repo = app_data.get('private_image', False)
    docker_username = app_data.get('docker_username', None)
    docker_email = app_data.get('docker_email', None)
    replicas = app_data.get('replicas', DEFAULT_REPLICAS)
    app_port = app_data.get('port', DEFAULT_APP_PORT)
    custom_domain = app_data.get('custom_domain', None)
    project = app_data.get('project', {})

    # Override with existing app data if provided
    if app:
        app_name = app.name
        app_alias = app.alias
        app_image = app.image
        command_string = app.command
        private_repo = app.private_image
        replicas = app.replicas
        app_port = app.port
        custom_domain = app.has_custom_domain

    command = command_string.split() if command_string else None

    return SimpleNamespace(
        app_name=app_name,
        app_alias=app_alias,
        app_image=app_image,
        command=command,
        command_string=command_string,
        env_vars=env_vars,
        private_repo=private_repo,
        docker_server=docker_server,
        docker_username=docker_username,
        docker_password=docker_password,
        docker_email=docker_email,
        replicas=replicas,
        app_port=app_port,
        custom_domain=custom_domain,
        is_notebook=is_notebook,
        is_modal=is_modal,
        is_ai=is_modal or is_notebook,
        model_server=model_server,
        project_id=project['id']
    )


def _create_app_object(app, extracted_data):
    """Create or update application object."""
    if app:
        return app
    else:
        return SimpleNamespace(
            name=extracted_data.app_name,
            image=extracted_data.app_image,
            project_id=extracted_data.project_id,
            alias=extracted_data.app_alias,
            port=extracted_data.app_port,
            command=extracted_data.command_string,
            replicas=extracted_data.replicas,
            private_image=extracted_data.private_repo,
        )


def _handle_image_pull_secret(kube_client, extracted_data, namespace, resource_registry):
    """Handle creation of image pull secrets for private repositories."""
    image_pull_secret = None

    if extracted_data.private_repo:
        image_pull_secret = create_docker_pull_secret(
            kube_client=kube_client,
            app_alias=extracted_data.app_alias,
            namespace=namespace,
            docker_username=extracted_data.docker_username,
            docker_password=extracted_data.docker_password,
            docker_email=extracted_data.docker_email,
            docker_server=extracted_data.docker_server
        )
        resource_registry['image_pull_secret'] = True

    elif (current_app.config.get('SYSTEM_DOCKER_EMAIL') and
          current_app.config.get('SYSTEM_DOCKER_PASSWORD')):
        try:
            kube_client.kube.read_namespaced_secret(
                DEFAULT_NAMESPACE_APP_NAME, namespace)
        except client.rest.ApiException as e:
            if e.status == 404:
                image_pull_secret = create_docker_pull_secret(
                    kube_client=kube_client,
                    app_alias=DEFAULT_NAMESPACE_APP_NAME,
                    namespace=namespace,
                    docker_username=current_app.config['SYSTEM_DOCKER_EMAIL'],
                    docker_password=current_app.config['SYSTEM_DOCKER_PASSWORD'],
                    docker_email=current_app.config['SYSTEM_DOCKER_EMAIL'],
                    docker_server=current_app.config['SYSTEM_DOCKER_SERVER']
                )
            else:
                raise
        resource_registry['image_pull_secret'] = True

    return image_pull_secret


def _create_deployment_spec(extracted_data, app_port, env_vars, image_pull_secret, volume_mount=None, volumes=None):
    """Create deployment specification with integrated container creation."""
    # Create environment variables
    env = []
    if env_vars:
        for key, value in env_vars.items():
            env.append(client.V1EnvVar(
                name=str(key), value=str(value)
            ))

    # Create container specification
    container = client.V1Container(
        name=extracted_data.app_alias,
        image=extracted_data.app_image,
        ports=[client.V1ContainerPort(container_port=app_port)],
        env=env,
        command=extracted_data.command,
        volume_mounts=[volume_mount] if volume_mount else None,
        resources={
            "limits": DEFAULT_RESOURCE_LIMITS,
            "requests": DEFAULT_RESOURCE_REQUESTS
        }
    )

    # Create pod template
    template = client.V1PodTemplateSpec(
        metadata=client.V1ObjectMeta(labels={
            'app': extracted_data.app_alias
        }),
        spec=client.V1PodSpec(
            containers=[container],
            image_pull_secrets=[
                image_pull_secret] if image_pull_secret else None,
            volumes=volumes
        )
    )

    # Create deployment
    return client.V1Deployment(
        api_version="apps/v1",
        kind="Deployment",
        metadata=client.V1ObjectMeta(
            name=f'{extracted_data.app_alias}-deployment'),
        spec=client.V1DeploymentSpec(
            replicas=extracted_data.replicas,
            template=template,
            selector={'matchLabels': {'app': extracted_data.app_alias}}
        )
    )


def _create_service_spec(extracted_data, service_port, app_port):
    """Create service specification."""
    service_name = f'{extracted_data.app_alias}-service'

    service_meta = client.V1ObjectMeta(
        name=service_name,
        labels={'app': extracted_data.app_alias}
    )

    service_spec = client.V1ServiceSpec(
        type='ClusterIP',
        ports=[client.V1ServicePort(
            port=int(service_port), target_port=app_port)],
        selector={'app': extracted_data.app_alias}
    )

    return client.V1Service(
        metadata=service_meta,
        spec=service_spec
    ), service_name


def _create_ingress_rule(service_name, service_port, sub_domain):
    """Create ingress rule for the application."""
    new_ingress_backend = client.V1IngressBackend(
        service=client.V1IngressServiceBackend(
            name=service_name,
            port=client.V1ServiceBackendPort(
                number=service_port
            )
        )
    )

    return client.V1IngressRule(
        host=sub_domain,
        http=client.V1HTTPIngressRuleValue(
            paths=[client.V1HTTPIngressPath(
                path="",
                path_type="ImplementationSpecific",
                backend=new_ingress_backend
            )]
        )
    )


def _handle_ingress_creation(kube_client, namespace, ingress_rule, project_alias):
    """Handle ingress creation or update."""
    ingress_name = f'{project_alias}-ingress'

    try:
        ingress_list = kube_client.networking_api.list_namespaced_ingress(
            namespace=namespace).items

        if not ingress_list:
            # Create new ingress
            ingress_meta = client.V1ObjectMeta(name=ingress_name)
            ingress_spec = {'rules': [ingress_rule]}
            ingress_body = {
                "apiVersion": "networking.k8s.io/v1",
                "kind": "Ingress",
                "metadata": ingress_meta,
                "spec": ingress_spec
            }

            kube_client.networking_api.create_namespaced_ingress(
                namespace=namespace,
                body=ingress_body
            )
            return True
        else:
            # Update existing ingress
            ingress = ingress_list[0]
            ingress.spec.rules.append(ingress_rule)
            kube_client.networking_api.patch_namespaced_ingress(
                name=ingress_name,
                namespace=namespace,
                body=ingress
            )
            return True
    except Exception as e:
        logger.error(f"Failed to create/update ingress: {str(e)}")
        return False


def deploy_user_app(kube_client, project, user=None, app=None, cluster=None, app_data={}):
    """
    Deploy an application to Kubernetes cluster.

    Args:
        kube_client: Kubernetes API client
        project: Project object
        user: User object (optional)
        app: Existing app object (optional)
        cluster: Cluster object (optional)
        app_data: Application configuration data

    Returns:
        SimpleNamespace: Application object or error response
    """
    resource_registry = _initialize_resource_registry()

    # Extract and validate app data
    extracted_data = _extract_app_data(app_data, app)
    if hasattr(extracted_data, 'status_code'):
        return extracted_data

    namespace = project.alias
    new_app = _create_app_object(app, extracted_data)
    app_alias = extracted_data.app_alias

    try:
        # Handle image pull secrets
        image_pull_secret = _handle_image_pull_secret(
            kube_client, extracted_data, namespace, resource_registry
        )

        # Handle PVC creation for AI notebooks
        new_volume_mount = None
        new_volumes = None
        service_port = current_app.config['KUBE_SERVICE_PORT']

        if extracted_data.is_ai and extracted_data.is_notebook:
            pvc_name = f'{app_alias}-pvc'
            new_app.is_ai = True
            mount_path = JUPYTER_MOUNT_PATH if extracted_data.is_notebook else DEFAULT_MOUNT_PATH
            new_app.is_notebook = True

            volumes, volume_mount = create_pvc(
                kube_client, pvc_name, namespace, mount_path=mount_path
            )
            new_volume_mount = volume_mount
            new_volumes = volumes
            resource_registry['pvc'] = True

        # Handle Seldon deployment for modal apps
        service_name = f'{app_alias}-service'
        seldon_deployment = None

        if extracted_data.is_modal:
            seldon_deployment = _create_seldon_deployment_by_type(
                kube_client, extracted_data, namespace, app_data
            )

            if isinstance(seldon_deployment, SimpleNamespace) and hasattr(seldon_deployment, 'status_code'):
                return seldon_deployment

            if seldon_deployment and seldon_deployment.service_append:
                service_name = f'{app_alias}-{seldon_deployment.service_append}'
            if seldon_deployment and seldon_deployment.ingress_append:
                custom_ingress_service_name = f'{app_alias}-{seldon_deployment.ingress_append}'

            service_port = extracted_data.app_port if extracted_data.app_port else seldon_deployment.port

            # Set common app properties
            new_app.port = service_port
            new_app.is_ai = True
            new_app.is_modal = True
            new_app.model_image_uri = app_data['model_image_uri']
            new_app.model_server = app_data['model_server']
            new_app.api_type = app_data['api_type']

            resource_registry['seldon_deployment'] = True
        else:

            # Create deployment specification
            deployment = _create_deployment_spec(
                extracted_data, extracted_data.app_port, extracted_data.env_vars,
                image_pull_secret, new_volume_mount, new_volumes
            )
            # Create standard deployment
            kube_client.appsv1_api.create_namespaced_deployment(
                body=deployment,
                namespace=namespace,
                _preload_content=False
            )
            resource_registry['app_deployment'] = True

            # Create service
            service, service_name = _create_service_spec(
                extracted_data, service_port, extracted_data.app_port
            )

            try:
                # Check if service exists and delete if necessary
                kube_client.kube.read_namespaced_service(
                    service_name, project.alias)
                kube_client.kube.delete_namespaced_service(
                    service_name, project.alias)
            except:
                pass

            kube_client.kube.create_namespaced_service(
                namespace=namespace,
                body=service,
                _preload_content=False
            )

        resource_registry['app_service'] = True

        # Handle custom domain or generate subdomain
        if extracted_data.custom_domain and user and user.is_beta_user:
            sub_domain = extracted_data.custom_domain
            app_data['has_custom_domain'] = True
        else:
            sub_domain = get_app_subdomain(
                extracted_data.app_alias, cluster.sub_domain)

        if 'custom_ingress_service_name' in locals():
            service_name = custom_ingress_service_name

        # Create ingress rule
        ingress_rule = _create_ingress_rule(
            service_name, service_port, sub_domain)

        if _handle_ingress_creation(kube_client, namespace, ingress_rule, project.alias):
            resource_registry['ingress_entry'] = True

        new_app.url = f'https://{sub_domain}'
        return new_app

    except client.rest.ApiException as e:
        logger.exception('Kubernetes API exception occurred')
        resource_clean_up(resource_registry,
                          extracted_data.app_alias, namespace, kube_client)
        return SimpleNamespace(
            message=json.loads(e.body),
            status_code=500
        )

    except Exception as e:
        logger.exception('Unexpected exception occurred')
        resource_clean_up(resource_registry,
                          extracted_data.app_alias, namespace, kube_client)
        return SimpleNamespace(
            message=str(e),
            status_code=500
        )


def _create_seldon_deployment_by_type(kube_client, extracted_data, namespace, app_data):
    """Create Seldon deployment based on model server type."""
    if extracted_data.model_server == 'MLFLOW_SERVER':
        return create_seldon_deployment_mlflow(
            kube_client=kube_client,
            app_alias=extracted_data.app_alias,
            namespace=namespace,
            model_uri=app_data['model_image_uri'],
            replicas=extracted_data.replicas
        )
    elif extracted_data.model_server == 'HUGGINGFACE_SERVER':
        return create_seldon_deployment_huggingface(
            kube_client=kube_client,
            app_alias=extracted_data.app_alias,
            namespace=namespace,
            model_uri=app_data['model_image_uri'],
            task=app_data['task'],
            replicas=extracted_data.replicas
        )
    else:
        return create_seldon_deployment(
            kube_client=kube_client,
            app_alias=extracted_data.app_alias,
            namespace=namespace,
            model_image_uri=app_data['model_image_uri'],
            replicas=extracted_data.replicas,
            api_type=app_data['api_type'],
            model_server=app_data['model_server']
        )


def create_pvc(kube_client, dep_name, namespace, mount_path=DEFAULT_MOUNT_PATH, storage=DEFAULT_STORAGE):
    """
    Create a Persistent Volume Claim (PVC) for the application.

    Args:
        kube_client: Kubernetes API client
        dep_name: Deployment name
        namespace: Kubernetes namespace
        mount_path: Volume mount path
        storage: Storage size

    Returns:
        tuple: (volumes, volume_mount) for pod specification
    """
    pvc_name = f'{dep_name}-pvc'
    pvc_meta = client.V1ObjectMeta(name=pvc_name)

    access_modes = ['ReadWriteOnce']
    resources = client.V1ResourceRequirements(
        requests=dict(storage=storage))

    pvc_spec = client.V1PersistentVolumeClaimSpec(
        access_modes=access_modes, resources=resources
    )

    pvc = client.V1PersistentVolumeClaim(
        api_version="v1",
        kind="PersistentVolumeClaim",
        metadata=pvc_meta,
        spec=pvc_spec
    )

    kube_client.kube.create_namespaced_persistent_volume_claim(
        namespace=namespace,
        body=pvc,
        _preload_content=False
    )

    # Pod volumes
    volumes = [client.V1Volume(
        name=dep_name,
        persistent_volume_claim=client.V1PersistentVolumeClaimVolumeSource(
            claim_name=pvc_name)
    )]

    # Define volume mount
    volume_mount = client.V1VolumeMount(
        mount_path=mount_path,
        name=dep_name
    )

    return volumes, volume_mount


def create_docker_pull_secret(kube_client, app_alias, namespace, docker_username, docker_password, docker_email, docker_server):
    """
    Create a docker pull secret for private repositories.

    Args:
        kube_client: Kubernetes API client
        app_alias: Application alias
        namespace: Kubernetes namespace
        docker_username: Docker registry username
        docker_password: Docker registry password
        docker_email: Docker registry email
        docker_server: Docker registry server

    Returns:
        V1LocalObjectReference: Image pull secret reference
    """
    # Handle GCR credentials
    if 'gcr' in docker_server and docker_username == '_json_key':
        docker_password = json.dumps(
            json.loads(base64.b64decode(docker_password))
        )

    # Create image pull secrets
    authstring = base64.b64encode(
        f'{docker_username}:{docker_password}'.encode("utf-8"))

    secret_dict = dict(auths={
        docker_server: {
            "username": docker_username,
            "password": docker_password,
            "email": docker_email,
            "auth": str(authstring, "utf-8")
        }
    })

    secret_b64 = base64.b64encode(
        json.dumps(secret_dict).encode("utf-8")
    )

    secret_body = client.V1Secret(
        metadata=client.V1ObjectMeta(name=app_alias),
        type='kubernetes.io/dockerconfigjson',
        data={'.dockerconfigjson': str(secret_b64, "utf-8")})

    kube_client.kube.create_namespaced_secret(
        namespace=namespace,
        body=secret_body,
        _preload_content=False)

    return client.V1LocalObjectReference(name=app_alias)


def update_app_env_vars(client, cluster_deployment, env_vars, delete_env_vars=[]):
    """
    Update environment variables for a Kubernetes deployment.

    Args:
        client: Kubernetes client
        cluster_deployment: Deployment object
        env_vars: New environment variables to add
        delete_env_vars: Environment variables to delete
    """
    container = cluster_deployment.spec.template.spec.containers[0]

    if env_vars:
        env = []
        env_list = container.env or []

        # Filter out environment variables to be deleted
        env_list = [
            env_var for env_var in env_list if env_var.name not in delete_env_vars]

        # Add new environment variables
        for key, value in env_vars.items():
            env.append(client.V1EnvVar(
                name=str(key), value=str(value)
            ))

        # Add existing app variables
        env.extend(env_list)
        container.env = env
    else:
        # Handle case where no new environment variables are provided
        container.env = [
            env_var for env_var in container.env if env_var.name not in delete_env_vars]


def delete_cluster_app(kube_client, namespace, app):
    """
    Delete application resources from Kubernetes cluster.

    Args:
        kube_client: Kubernetes API client
        namespace: Kubernetes namespace
        app: Application object

    Returns:
        tuple: (response_dict, status_code) or None
    """
    deployment_name = f'{app.alias}-deployment'
    service_name = f'{app.alias}-service'

    try:
        # Delete deployment
        deployment = kube_client.appsv1_api.read_namespaced_deployment(
            name=deployment_name,
            namespace=namespace
        )

        if deployment:
            kube_client.appsv1_api.delete_namespaced_deployment(
                name=deployment_name,
                namespace=namespace
            )

        # Delete service
        service = kube_client.kube.read_namespaced_service(
            name=service_name,
            namespace=namespace
        )

        if service:
            kube_client.kube.delete_namespaced_service(
                name=service_name,
                namespace=namespace
            )

        # Delete secret
        secret = kube_client.kube.read_namespaced_secret(
            name=app.alias,
            namespace=namespace
        )
        kube_client.kube.delete_namespaced_secret(
            name=app.alias,
            namespace=namespace
        )
    except Exception as e:
        logger.exception('Exception occurred during app deletion')
        if hasattr(e, 'status') and e.status != 404:
            return dict(status='fail', message=str(e)), 500

    # Delete PVC
    pvc_name = f'{app.alias}-pvc'
    try:
        pvc = kube_client.kube.read_namespaced_persistent_volume_claim(
            name=pvc_name,
            namespace=namespace
        )

        if pvc:
            kube_client.kube.delete_namespaced_persistent_volume_claim(
                name=pvc_name,
                namespace=namespace
            )
    except:
        pass


def check_kube_error_code(error):
    """
    Check and return appropriate error code for Kubernetes errors.

    Args:
        error: Error code

    Returns:
        int: Appropriate HTTP status code
    """
    # Prevent a 401 from being sent to the frontend
    return 511 if error == 401 else error


def create_seldon_deployment(kube_client, app_alias, namespace, model_image_uri, replicas, api_type, model_server):
    """
    Create a generic Seldon deployment.

    Args:
        kube_client: Kubernetes API client
        app_alias: Application alias
        namespace: Kubernetes namespace
        model_image_uri: Model image URI
        replicas: Number of replicas
        api_type: API type
        model_server: Model server type

    Returns:
        SimpleNamespace: Deployment result or error response
    """
    sdep_body = {
        "apiVersion": "machinelearning.seldon.io/v1",
        "kind": "SeldonDeployment",
        "metadata": {
            "name": f"{app_alias}",
            "namespace": namespace
        },
        "spec": {
            "name": app_alias,
            "predictors": [{
                "name": DEFAULT_SERVICE_APPEND,
                "replicas": replicas,
                "graph": {
                    "name": "classifier",
                    "implementation": model_server,
                    "modelUri": model_image_uri,
                    "type": "MODEL",
                    "endpoint": {
                        "type": api_type
                    }
                }
            }]
        }
    }

    try:
        kube_client.custom_api.create_namespaced_custom_object(
            group="machinelearning.seldon.io",
            version="v1",
            namespace=namespace,
            plural="seldondeployments",
            body=sdep_body
        )
        return SimpleNamespace(
            service_append=DEFAULT_SERVICE_APPEND,
            port=DEFAULT_PORT
        )
    except client.rest.ApiException as e:
        logger.exception('Seldon Deployment creation failed')
        return SimpleNamespace(
            message=json.loads(e.body),
            status_code=500
        )


def create_seldon_deployment_mlflow(kube_client, app_alias, namespace, model_uri, replicas=1):
    """
    Create a MLflow-specific Seldon deployment.

    Args:
        kube_client: Kubernetes API client
        app_alias: Application alias
        namespace: Kubernetes namespace
        model_uri: Model URI
        replicas: Number of replicas

    Returns:
        SimpleNamespace: Deployment result or error response
    """
    sdep_body = {
        "apiVersion": "machinelearning.seldon.io/v1",
        "kind": "SeldonDeployment",
        "metadata": {
            "name": f"{app_alias}",
            "namespace": namespace
        },
        "spec": {
            "name": app_alias,
            "predictors": [{
                "name": DEFAULT_SERVICE_APPEND,
                "replicas": replicas,
                "graph": {
                    "name": "classifier",
                    "implementation": "MLFLOW_SERVER",
                    "modelUri": "file:///mnt/models",  # Matches the initContainer's extraction path
                    "children": []
                },
                "componentSpecs": [{
                    "spec": {
                        "initContainers": [{
                            "name": "classifier-model-initializer",
                            "image": "khalifan1126/cc-mlflow-storage-initialiser:amd1",
                            "imagePullPolicy": "IfNotPresent",
                            "env": [
                                {
                                    "name": "MODEL_URI",
                                    "value": model_uri
                                },
                                {
                                    "name": "MLFLOW_TRACKING_URI",
                                    "value": current_app.config['MLFLOW_TRACKING_URI']
                                }
                            ],
                            "terminationMessagePath": "/dev/termination-log",
                            "terminationMessagePolicy": "File",
                            "volumeMounts": [
                                {
                                    "mountPath": "/mnt/models",
                                    "name": "classifier-provision-location"
                                }
                            ]
                        }],
                        "containers": [{
                            "name": "classifier",
                            "imagePullPolicy": "IfNotPresent",
                            "volumeMounts": [
                                {
                                    "mountPath": "/mnt/models",
                                    "name": "classifier-provision-location"
                                }
                            ],
                            "livenessProbe": {
                                "initialDelaySeconds": 80,
                                "failureThreshold": 200,
                                "periodSeconds": 5,
                                "successThreshold": 1,
                                "httpGet": {
                                    "path": "/health/ping",
                                    "port": 9000,
                                    "scheme": "HTTP"
                                }
                            },
                            "readinessProbe": {
                                "initialDelaySeconds": 80,
                                "failureThreshold": 200,
                                "periodSeconds": 5,
                                "successThreshold": 1,
                                "httpGet": {
                                    "path": "/health/ping",
                                    "port": 9000,
                                    "scheme": "HTTP"
                                }
                            }
                        }],
                        "volumes": [
                            {
                                "name": "classifier-provision-location",
                                "emptyDir": {}
                            }
                        ]
                    }
                }]
            }]
        }
    }

    try:
        kube_client.custom_api.create_namespaced_custom_object(
            group="machinelearning.seldon.io",
            version="v1",
            namespace=namespace,
            plural="seldondeployments",
            body=sdep_body
        )
        return SimpleNamespace(
            service_append=DEFAULT_SERVICE_APPEND,
            port=DEFAULT_PORT
        )
    except client.rest.ApiException as e:
        logger.exception('Seldon MLflow Deployment creation failed')
        return SimpleNamespace(
            message=json.loads(e.body),
            status_code=500
        )


def create_seldon_deployment_huggingface(kube_client, app_alias, namespace, model_uri, task, replicas=1):
    """
    Create a Hugging Face-specific Seldon deployment.

    Args:
        kube_client: Kubernetes API client
        app_alias: Application alias
        namespace: Kubernetes namespace
        model_uri: Model URI
        task: Model task type
        replicas: Number of replicas

    Returns:
        SimpleNamespace: Deployment result or error response
    """
    ingress_append = "default-transformer"

    # Model settings for Hugging Face deployments
    model_settings_json = json.dumps({
        "name": f"{app_alias}",
        "implementation": "mlserver_huggingface.runtime.HuggingFaceRuntime",
        "parameters": {
            "extra": {
                "task": task,
                "pretrained_model": model_uri,
            }
        }
    }).replace('"', '\\"')

    sdep_body = {
        "apiVersion": "machinelearning.seldon.io/v1",
        "kind": "SeldonDeployment",
        "metadata": {
            "name": f"{app_alias}",
            "namespace": namespace,
        },
        "spec": {
            "protocol": "v2",
            "predictors": [{
                "name": "default",
                "graph": {
                    "name": "transformer",
                    "implementation": "HUGGINGFACE_SERVER",
                    "children": [],
                    "parameters": [
                        {
                            "name": "task",
                            "value": task,
                            "type": "STRING"
                        },
                        {
                            "name": "pretrained_model",
                            "value": model_uri,
                            "type": "STRING"
                        },
                    ]
                },
                "componentSpecs": [{
                    "spec": {
                        # Prevent deployment on non GPU node
                        "nodeSelector": {
                            "nvidia.com/gpu.present": "true"
                        },
                        "tolerations": [
                            {
                                "key": "nvidia.com/gpu",
                                "operator": "Exists",
                                "effect": "NoSchedule"
                            }
                        ],
                        # Unloads the model-settings.json file
                        "initContainers": [
                            {
                                "name": "write-model-settings",
                                "image": "python:3.9-slim",
                                "command": ["sh", "-c"],
                                "args": [
                                    f"""
                                    echo 'Writing model-settings.json...'; \
                                    echo \"{model_settings_json}\" > /mnt/models/model-settings.json; \
                                    echo 'Contents of model-settings.json:'; \
                                    cat /mnt/models/model-settings.json; \
                                    echo 'Done writing model-settings.json.'
                                    """
                                ],
                                "volumeMounts": [
                                    {
                                        "name": "transformer-provision-location",
                                        "mountPath": "/mnt/models"
                                    }
                                ]
                            }
                        ],
                        "containers": [
                            {
                                "name": "transformer",
                                "imagePullPolicy": "IfNotPresent",
                                "env": [
                                    {"name": "MLSERVER_DEBUG", "value": "true"},
                                    {"name": "PYTHONUNBUFFERED", "value": "1"},
                                    {"name": "MLSERVER_MODEL_NAME",
                                        "value": "models"},
                                    {"name": "GOMAXPROCS", "value": "2"},
                                    {"name": "OMP_NUM_THREADS", "value": "1"},
                                    {"name": "MKL_NUM_THREADS", "value": "1"},
                                    {"name": "OPENBLAS_NUM_THREADS", "value": "1"},
                                    {"name": "MLSERVER_MODEL_PARAMETERS", "value": json.dumps({
                                        "uri": model_uri,
                                        "extra": {
                                            "task": task
                                        }
                                    })}
                                ],
                                "ports": [{
                                    "containerPort": HUGGINGFACE_PORT,
                                    "name": "http",
                                    "protocol": "TCP"
                                }],
                                "volumeMounts": [
                                    {
                                        "name": "transformer-provision-location",
                                        "mountPath": "/mnt/models"
                                    }
                                ],
                                "livenessProbe": {
                                    "httpGet": {
                                        "path": "/v2/health/live",
                                        "port": "http"
                                    },
                                    "initialDelaySeconds": 60,
                                    "periodSeconds": 10,
                                    "timeoutSeconds": 5,
                                    "failureThreshold": 3
                                },
                                "readinessProbe": {
                                    "httpGet": {
                                        "path": "/v2/health/ready",
                                        "port": "http"
                                    },
                                    "initialDelaySeconds": 60,
                                    "periodSeconds": 5,
                                    "timeoutSeconds": 5,
                                    "failureThreshold": 3
                                },
                                "resources": {
                                    "limits": GPU_RESOURCE_LIMITS,
                                    "requests": GPU_RESOURCE_REQUESTS
                                }
                            }
                        ],
                        "volumes": [
                            {
                                "name": "transformer-provision-location",
                                "emptyDir": {}
                            }
                        ]
                    }
                }],
                "replicas": replicas
            }]
        }
    }

    try:
        kube_client.custom_api.create_namespaced_custom_object(
            group="machinelearning.seldon.io",
            version="v1",
            namespace=namespace,
            plural="seldondeployments",
            body=sdep_body
        )
        return SimpleNamespace(
            service_append=DEFAULT_SERVICE_APPEND,
            ingress_append=ingress_append,
            port=HUGGINGFACE_PORT
        )
    except client.rest.ApiException as e:
        logger.exception('Seldon Huggingface Deployment creation failed')
        return SimpleNamespace(
            message=json.loads(e.body),
            status_code=500
        )
