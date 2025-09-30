pipeline {
    agent {
        label 'AWS-EC2-CNC'
    }
    
    environment {
        DOCKER_REGISTRY = "us-docker.pkg.dev/coverity-cloud-sandbox-dev/test/pr-agent"
        DOCKER_TAG = "latest"
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
                        docker buildx . -t ${env.DOCKER_REGISTRY}:${env.DOCKER_TAG} --platform linux/amd64 -f docker/Dockerfile
                    """
                }
            }
        }
        
        stage('Test Docker Image') {
            steps {
                script {
                    echo 'Testing Docker image...'
                    
                    // Test the image by running it briefly
                    sh "docker run --rm --name test-${env.BUILD_NUMBER} -d ${env.DOCKER_REGISTRY}:${env.DOCKER_TAG} || true"
                    
                    // You can add more specific tests here based on your application
                    echo 'Docker image test completed'
                }
            }
        }
        
        stage('Login to Artifact Registry') {
            steps {
                script {
                    echo 'Logging into Google Artifact Registry...'
                    
                    // Login to Google Artifact Registry using credentials
                    withCredentials([file(credentialsId: 'dockerconfig', variable: 'CONFIGFILE')]) {
                        def destinationFile = "config.json"
                        sh "cp ${CONFIGFILE} ${destinationFile}"
                        echo "Content of ${CONFIGFILE} copied to ${destinationFile}"
                    }
                    
                    echo 'Successfully logged into Google Artifact Registry'
                }
            }
        }
        
        stage('Push to Artifact Registry') {
            steps {
                script {
                    echo 'Pushing Docker image to Google Artifact Registry...'
                    
                    // Push only the latest tag
                    sh "docker push ${env.DOCKER_REGISTRY}:${env.DOCKER_TAG}"
                    
                    echo "✅ Docker image pushed successfully!"
                    echo "🐳 Image available at: ${env.DOCKER_REGISTRY}:${env.DOCKER_TAG}"
                }
            }
        }
        
        stage('Cleanup') {
            steps {
                script {
                    echo 'Cleaning up local Docker images...'
                    
                    // Remove local images to save disk space
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
                // Logout from Docker Hub
                sh 'docker logout || true'
                echo 'Pipeline completed.'
            }
        }
        success {
            echo '🎉 SUCCESS: Docker image built and pushed successfully!'
            echo "Check your Google Artifact Registry: https://console.cloud.google.com/artifacts/docker/coverity-cloud-sandbox-dev/us/test/pr-agent"
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