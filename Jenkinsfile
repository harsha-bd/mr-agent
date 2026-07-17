pipeline {
    agent {
        label 'AWS-EC2-CYPRESS-SUDO'
    }

    environment {
        GIT_CREDENTIALS  = 'GithubCredentials'
        DOCKER_REGISTRY  = "us-docker.pkg.dev/coverity-cloud-sandbox-dev/test/mr-agent"
        DOCKER_TAG       = "latest"
    }

    triggers {
        // Trigger on push to main branch
        githubPush()
    }

    stages {
        stage('Checkout Repository') {
            steps {
                script {
                    echo "////CHECKING OUT MR-AGENT REPO////"
                    git branch: 'main',
                        changelog: false,
                        credentialsId: "${GIT_CREDENTIALS}",
                        poll: false,
                        url: 'https://github.com/harsha-bd/mr-agent.git'
                }
            }
        }

        stage('Build Docker Image') {
            steps {
                script {
                    echo 'Login to docker...'
                    withCredentials([file(credentialsId: 'dockerconfig', variable: 'CONFIGFILE')]) {
                        sh '''
                            mkdir -p ~/.docker
                            cp "$CONFIGFILE" ~/.docker/config.json
                            chmod 600 ~/.docker/config.json
                        '''
                        sh """
                            docker build -t ${env.DOCKER_REGISTRY}:${env.DOCKER_TAG} -f docker/Dockerfile .
                            docker run --rm --name test-${env.BUILD_NUMBER} -d ${env.DOCKER_REGISTRY}:${env.DOCKER_TAG} || true
                            docker push ${env.DOCKER_REGISTRY}:${env.DOCKER_TAG}
                        """
                    }
                }
            }
        }

        stage('Cleanup') {
            steps {
                script {
                    echo 'Cleaning up local Docker images...'
                    sh """
                        docker rmi ${env.DOCKER_REGISTRY}:${env.DOCKER_TAG} || true
                        docker system prune -f || true
                    """
                    echo 'Cleanup completed'
                }
            }
        }
    }

    post {
        always {
            script {
                sh 'rm -f ~/.docker/config.json || true'
                sh 'docker logout us-docker.pkg.dev || true'
                echo 'Pipeline completed.'
            }
        }
        success {
            echo '🎉 SUCCESS: Docker image built and pushed successfully!'
            echo "Check your Google Artifact Registry: https://console.cloud.google.com/artifacts/docker/coverity-cloud-sandbox-dev/us/test/mr-agent"
        }
        failure {
            echo '❌ FAILURE: Pipeline failed. Check the logs for details.'
        }
        cleanup {
            script {
                sh 'docker system prune -f || true'
                echo 'Final cleanup completed'
            }
        }
    }
}