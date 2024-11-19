from app.helpers.alias import create_alias
from flask import current_app
from types import SimpleNamespace
from kubernetes import client
import base64
import json
from app.helpers.clean_up import resource_clean_up
from app.helpers.crane_app_logger import logger


def get_app_subdomain(alias, domain):

    return f'{alias}.{domain}'


def create_kube_clients(kube_host, kube_token):
    # configure client
    config = client.Configuration()
    config.host = kube_host
    config.api_key['authorization'] = kube_token
    config.api_key_prefix['authorization'] = 'Bearer'
    config.verify_ssl = False
    # config.assert_hostname = False

    # create API instance
    api_client = client.ApiClient()
    kube = client.CoreV1Api(client.ApiClient(config))
    # extension_api = client.ExtensionsV1beta1Api(client.ApiClient(config))
    appsv1_api = client.AppsV1Api(client.ApiClient(config))
    batchv1_api = client.BatchV1Api(client.ApiClient(config))
    storageV1Api = client.StorageV1Api(client.ApiClient(config))
    networking_api = client.NetworkingV1Api(client.ApiClient(config))

    # return kube, extension_api, appsv1_api, api_client, batchv1_api, storageV1Api
    return SimpleNamespace(
        kube=kube,
        # extension_api=extension_api,
        networking_api=networking_api,
        appsv1_api=appsv1_api,
        api_client=api_client,
        batchv1_api=batchv1_api,
        storageV1Api=storageV1Api
    )


def deploy_user_app(kube_client, project, user=None, app=None, cluster=None, app_data={}):
    """
    deploy an application
    """

    resource_registry = {
        'db_deployment': False,
        'db_service': False,
        'image_pull_secret': False,
        'app_deployment': False,
        'app_service': False,
        'ingress_entry': False
    }

    is_notebook = app_data.get('is_notebook', False)
    app_name = app_data.get('name', None)
    if is_notebook:
        if not app_name:
            return SimpleNamespace(
                message='Missing data for required field, name',
                status_code=400
            )
        notebook_data = {
            'image': 'cranecloud/jupyter-notebook:latest',
            'port': 8888,
            'is_ai': True,
            'is_notebook': True,
            'name': app_name
        }
        app_data.update(notebook_data)

    # check images existence
    app_image = app_data.get('image', None)
    docker_server = app_data.get(
        'docker_server', 'docker.io')
    docker_password = app_data.get('docker_password', None)
    # should be a docker hub image
    # if 'gcr' not in docker_server:
    #     validate_docker_image = docker_image_checker(
    #         app_image, docker_password, project)
    #     if validate_docker_image != True:
    #         return SimpleNamespace(
    #             message=validate_docker_image,
    #             status_code=404
    #         )

    app_alias = create_alias(app_name)
    command_string = app_data.get('command', None)
    # env_vars = app_data['env_vars']
    env_vars = app_data.get('env_vars', None)
    private_repo = app_data.get('private_image', False)
    docker_server = app_data.get('docker_server', 'docker.io')
    docker_username = app_data.get('docker_username', None)
    docker_password = app_data.get('docker_password', None)
    docker_email = app_data.get('docker_email', None)
    replicas = app_data.get('replicas', 1)
    app_port = app_data.get('port', 80)
    custom_domain = app_data.get('custom_domain', None)
    image_pull_secret = None

    if app:
        app_name = app.name
        app_alias = app.alias
        app_image = app.image
        command_string = app.command
        private_repo = app.private_image
        replicas = app.replicas
        app_port = app.port
        custom_domain = app.has_custom_domain
        image_pull_secret = None

    command = command_string.split() if command_string else None

    namespace = project.alias

    try:

        if app:
            new_app = app
        else:
            new_app = SimpleNamespace(
                name=app_name,
                image=app_image,
                project_id=project.id,
                alias=app_alias,
                port=app_port,
                command=command_string,
                replicas=replicas,
                private_image=private_repo
            )

        if private_repo:
            image_pull_secret = create_docker_pull_secret(
                kube_client=kube_client,
                app_alias=app_alias,
                namespace=namespace,
                docker_username=docker_username,
                docker_password=docker_password,
                docker_email=docker_email,
                docker_server=docker_server
            )
            # update registry
            resource_registry['image_pull_secret'] = True

        elif current_app.config['SYSTEM_DOCKER_EMAIL'] and current_app.config['SYSTEM_DOCKER_PASSWORD']:
            DEFAULT_NAMESPACE = namespace
            DEFAULT_APP_NAME = 'cranecloud-app'
            try:
                kube_client.kube.read_namespaced_secret(
                    DEFAULT_APP_NAME, DEFAULT_NAMESPACE)
            except client.rest.ApiException as e:
                if e.status == 404:
                    image_pull_secret = create_docker_pull_secret(
                        kube_client=kube_client,
                        app_alias=DEFAULT_APP_NAME,
                        namespace=DEFAULT_NAMESPACE,
                        docker_username=current_app.config['SYSTEM_DOCKER_EMAIL'],
                        docker_password=current_app.config['SYSTEM_DOCKER_PASSWORD'],
                        docker_email=current_app.config['SYSTEM_DOCKER_EMAIL'],
                        docker_server=current_app.config['SYSTEM_DOCKER_SERVER']
                    )
                else:
                    raise

            # update registry
            resource_registry['image_pull_secret'] = True

         # create deployment
        dep_name = f'{app_alias}-deployment'

        mount_path = '/data'

        # create app deployment's pvc meta and spec
        is_ai = app_data.get('is_ai', False)
        if is_ai:
            pvc_name = f'{app_alias}-pvc'
            new_app.is_ai = True
            if is_notebook:
                mount_path = '/home/jovyan/work'
                new_app.is_notebook = True
            volumes, volume_mount = create_pvc(
                kube_client, pvc_name, namespace, mount_path=mount_path)

        # EnvVar
        env = []
        if env_vars:
            for key, value in env_vars.items():
                env.append(client.V1EnvVar(
                    name=str(key), value=str(value)
                ))

        # pod template
        container = client.V1Container(
            name=app_alias,
            image=app_image,
            ports=[client.V1ContainerPort(container_port=app_port)],
            env=env,
            command=command,
            volume_mounts=[volume_mount] if is_ai else None
        )

        # spec
        template = client.V1PodTemplateSpec(
            metadata=client.V1ObjectMeta(labels={
                'app': app_alias
            }),
            spec=client.V1PodSpec(
                containers=[container],
                image_pull_secrets=[image_pull_secret],
                volumes=volumes if is_ai else None
            )
        )

        # spec of deployment
        spec = client.V1DeploymentSpec(
            replicas=replicas,
            template=template,
            selector={'matchLabels': {'app': app_alias}}
        )

        # Instantiate the deployment
        deployment = client.V1Deployment(
            api_version="apps/v1",
            kind="Deployment",
            metadata=client.V1ObjectMeta(name=dep_name),
            spec=spec
        )

        # create deployment in  cluster

        kube_client.appsv1_api.create_namespaced_deployment(
            body=deployment,
            namespace=namespace,
            _preload_content=False
        )

        # update registry
        resource_registry['app_deployment'] = True

        # create service in the cluster
        service_name = f'{app_alias}-service'

        service_meta = client.V1ObjectMeta(
            name=service_name,
            labels={'app': app_alias}
        )

        service_spec = client.V1ServiceSpec(
            type='ClusterIP',
            ports=[client.V1ServicePort(
                port=int(current_app.config['KUBE_SERVICE_PORT']), target_port=app_port)],
            selector={'app': app_alias}
        )

        service = client.V1Service(
            metadata=service_meta,
            spec=service_spec)

        try:
            # Check if service exists in the cluster
            kube_client.kube.read_namespaced_service(
                service_name, project.alias)
            # Delete service
            kube_client.kube.delete_namespaced_service(
                service_name, project.alias)
        except:
            pass

        kube_client.kube.create_namespaced_service(
            namespace=namespace,
            body=service,
            _preload_content=False
        )

        # update resource registry
        resource_registry['app_service'] = True

        if custom_domain and user.is_beta_user:
            sub_domain = custom_domain
            app_data['has_custom_domain'] = True

        else:
            sub_domain = get_app_subdomain(
                app_alias, cluster.sub_domain)

        # create new ingres rule for the application
        new_ingress_backend = client.V1IngressBackend(
            service=client.V1IngressServiceBackend(
                name=service_name,
                port=client.V1ServiceBackendPort(
                    number=current_app.config['KUBE_SERVICE_PORT']
                )
            )
        )

        new_ingress_rule = client.V1IngressRule(
            host=sub_domain,
            http=client.V1HTTPIngressRuleValue(
                paths=[client.V1HTTPIngressPath(
                    path="",
                    path_type="ImplementationSpecific",
                    backend=new_ingress_backend
                )]
            )
        )

        ingress_name = f'{project.alias}-ingress'

        # Check if there is an ingress resource in the namespace, create if not

        ingress_list = kube_client.networking_api.list_namespaced_ingress(
            namespace=namespace).items

        if not ingress_list:

            ingress_meta = client.V1ObjectMeta(
                name=ingress_name
            )

            ingress_spec = {
                'rules': [new_ingress_rule]
            }

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

            # update registry
            resource_registry['ingress_entry'] = True
        else:
            # Update ingress with new entry
            ingress = ingress_list[0]

            ingress.spec.rules.append(new_ingress_rule)

            kube_client.networking_api.patch_namespaced_ingress(
                name=ingress_name,
                namespace=namespace,
                body=ingress
            )

        service_url = f'https://{sub_domain}'

        new_app.url = service_url

        saved = new_app.save()

        # if not saved:
        # log_activity('App', status='Failed',
        #              operation='Create',
        #              description='Internal Server Error',
        #              a_project=project,
        #              a_cluster_id=project.cluster_id)
        # return SimpleNamespace(
        #     message='Internal Server Error',
        #     status_code=500
        # )

        # log_activity('App', status='Success',
        #              operation='Create',
        #              description='Created app Successfully',
        #              a_project=project,
        #              a_cluster_id=project.cluster_id,
        #              a_app=new_app)
        return new_app

    except client.rest.ApiException as e:
        logger.exception('Exception occurred')
        resource_clean_up(
            resource_registry,
            app_alias,
            namespace,
            kube_client
        )

        # log_activity('App', status='Failed',
        #              operation='Create',
        #              description=json.loads(e.body),
        #              a_project=project,
        #              a_cluster_id=project.cluster_id,
        #              )

        return SimpleNamespace(
            message=json.loads(e.body),
            status_code=500
        )

    except Exception as e:
        logger.exception('Exception occurred')
        resource_clean_up(
            resource_registry,
            app_alias,
            namespace,
            kube_client
        )
        # log_activity('App', status='Failed',
        #              operation='Create',
        #              description=str(e),
        #              a_project=project,
        #              a_cluster_id=project.cluster_id,
        #              )

        return SimpleNamespace(
            message=str(e),
            status_code=500
        )


def create_pvc(kube_client, dep_name, namespace, mount_path='/data', storage='1Gi'):
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
    """Create a docker pull secret for repositories"""

    # handle gcr credentials
    if 'gcr' in docker_server and docker_username == '_json_key':
        docker_password = json.dumps(
            json.loads(base64.b64decode(docker_password))
        )

    # create image pull secrets
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

    image_pull_secret = client.V1LocalObjectReference(
        name=app_alias)
    return image_pull_secret


def update_app_env_vars(client, cluster_deployment, env_vars, delete_env_vars=[]):
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
    # delete deployment and service for the app

    deployment_name = f'{app.alias}-deployment'
    service_name = f'{app.alias}-service'
    try:

        deployment = kube_client.appsv1_api.read_namespaced_deployment(
            name=deployment_name,
            namespace=namespace
        )

        if deployment:
            kube_client.appsv1_api.delete_namespaced_deployment(
                name=deployment_name,
                namespace=namespace
            )

        service = kube_client.kube.read_namespaced_service(
            name=service_name,
            namespace=namespace
        )

        if service:
            kube_client.kube.delete_namespaced_service(
                name=service_name,
                namespace=namespace
            )

        secret = kube_client.kube.read_namespaced_secret(
            name=app.alias,
            namespace=namespace
        )
        kube_client.kube.delete_namespaced_secret(
            name=app.alias,
            namespace=namespace
        )
    except Exception as e:
        logger.exception('Exception occurred')
        if e.status != 404:
            return dict(status='fail', message=str(e)), 500

    # delete pvc
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
    # prevent a 401 from being sent to the frontend
    return 511 if error == 401 else error
