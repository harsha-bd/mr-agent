pipeline {
    agent any
    environment {
        // Define your Docker Hub repository and credentials
        DOCKERHUB_REPOSITORY = "harsham1/mr-agent"
        DOCKER_TAG = "latest"
        DOCKERHUB_CREDENTIALS = 'docker-hub-credentials'
    }
    triggers {
        // Trigger on push to main branch
        githubPush()
    }
    stages {
        stage('Checkout') {
            steps {
                echo 'Checking out source code...'
                checkout scm
            }
        }
        stage('Build and Push Multi-Arch Image') {
            steps {
                script {
                    echo 'Logging into Docker Hub...'
                    withCredentials([usernamePassword(credentialsId: "${env.DOCKERHUB_CREDENTIALS}",
                                                    usernameVariable: 'DOCKER_USERNAME',
                                                    passwordVariable: 'DOCKER_PASSWORD')]) {
                        sh 'echo $DOCKER_PASSWORD | docker login -u $DOCKER_USERNAME --password-stdin'
                    }

                    // Set up multi-architecture support using buildx
                    sh """
                        docker buildx create --use --name mybuilder
                    """

                    // Build and push the image for both linux/amd64 and linux/arm64
                    sh """
                        docker buildx build \\
                          --builder mybuilder \\
                          --platform linux/amd64,linux/arm64 \\
                          --tag ${env.DOCKERHUB_REPOSITORY}:${env.DOCKER_TAG} \\
                          --push \\
                          -f docker/Dockerfile .
                    """
                }
            }
        }

        stage('Cleanup') {
            steps {
                script {
                    echo 'Cleaning up builder and logging out...'
                    sh 'docker logout || true'
                    sh 'docker buildx rm mybuilder || true'
                }
            }
        }
    }

    post {
        success {
            echo '🎉 SUCCESS: Multi-architecture Docker image built and pushed successfully!'
            echo "🐳 Image available at: ${env.DOCKERHUB_REPOSITORY}:${env.DOCKER_TAG}"
        }
        failure {
            echo '❌ FAILURE: Pipeline failed. Check the logs for details.'
        }
    }
}
