'''A Kubernetes Python Pulumi program to deploy kebab-zrb-app-name'''

from dotenv import dotenv_values
from pulumi_kubernetes.helm.v3 import Chart, LocalChartOpts
import pulumi
import os

CURRENT_DIR = os.path.dirname(__file__)
APP_DIR = os.path.abspath(os.path.join(CURRENT_DIR, '..', 'src'))
TEMPLATE_ENV_FILE_NAME = os.path.join(APP_DIR, 'template.env')
NAMESPACE = os.getenv('NAMESPACE', 'default')

image = os.getenv('IMAGE', 'kebab-zrb-app-name:latest')
replica = int(os.getenv('REPLICA', '1'))
app_labels = {'app': 'kebab-zrb-app-name'}
env_map = dotenv_values(TEMPLATE_ENV_FILE_NAME)
app_port = int(os.getenv('APP_PORT', env_map.get('APP_PORT', '8080')))

# https://www.pulumi.com/registry/packages/kubernetes/api-docs/helm/v3/chart/#local-chart-directory  # noqa
release = Chart(
    'kebab-zrb-app-name',
    LocalChartOpts(
        path='./helm-charts/kebab-zrb-app-name',
        namespace=NAMESPACE,
        values={

        }
    )
)

pulumi.export('deployment-chart', release.metadata['name'])
