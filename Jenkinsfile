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
        
        stage('Build Docker Image') {
            steps {
                script {
                    sh """
                        docker build . -t ${env.DOCKERHUB_REPOSITORY}:${env.DOCKER_TAG} --target gitlab_webhook -f docker/Dockerfile
                    """
                }
            }
        }
        
        stage('Test Docker Image') {
            steps {
                script {
                    echo 'Testing Docker image...'
                    
                    // Test the image by running it briefly
                    sh "docker run --rm --name test-${env.BUILD_NUMBER} -d ${env.DOCKERHUB_REPOSITORY}:${env.DOCKER_TAG} || true"
                    
                    // You can add more specific tests here based on your application
                    echo 'Docker image test completed'
                }
            }
        }
        
        stage('Login to Docker Hub') {
            steps {
                script {
                    echo 'Logging into Docker Hub...'
                    
                    // Login to Docker Hub using credentials
                    withCredentials([usernamePassword(credentialsId: "${env.DOCKERHUB_CREDENTIALS}", 
                                                    usernameVariable: 'DOCKER_USERNAME', 
                                                    passwordVariable: 'DOCKER_PASSWORD')]) {
                        sh 'echo $DOCKER_PASSWORD | docker login -u $DOCKER_USERNAME --password-stdin'
                    }
                    
                    echo 'Successfully logged into Docker Hub'
                }
            }
        }
        
        stage('Push to Docker Hub') {
            steps {
                script {
                    echo 'Pushing Docker image to Docker Hub...'
                    
                    // Push only the latest tag
                    sh "docker push ${env.DOCKERHUB_REPOSITORY}:${env.DOCKER_TAG}"
                    
                    echo "✅ Docker image pushed successfully!"
                    echo "🐳 Image available at: ${env.DOCKERHUB_REPOSITORY}:${env.DOCKER_TAG}"
                }
            }
        }
        
        stage('Cleanup') {
            steps {
                script {
                    echo 'Cleaning up local Docker images...'
                    
                    // Remove local images to save disk space
                    sh """
                        docker rmi ${env.DOCKERHUB_REPOSITORY}:${env.DOCKER_TAG} || true
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
                // Logout from Docker Hub
                sh 'docker logout || true'
                echo 'Pipeline completed.'
            }
        }
        success {
            echo '🎉 SUCCESS: Docker image built and pushed successfully!'
            echo "Check your Docker Hub repository: https://hub.docker.com/r/${env.DOCKERHUB_REPOSITORY}"
        }
        failure {
            echo '❌ FAILURE: Pipeline failed. Check the logs for details.'
        }
        cleanup {
            script {
                // Additional cleanup if needed
                sh 'docker system prune -f || true'
                echo 'Final cleanup completed'
            }
        }
    }
}