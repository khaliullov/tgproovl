node {
    def app
    def image

    stage('Clone repository') {
       copyFilesToWorkSpace()
    }

    stage('Build image') {
        image = "${env.REGISTRY}/${env.GITHUB_REPOSITORY}:0.0.1"
        app = docker.build(image)
    }

    stage('Push image') {
        withCredentials([usernamePassword(credentialsId: 'docker-hub-credentials', usernameVariable: "${env.REGISTRY_USERNAME}", passwordVariable: "${env.REGISTRY_PASSWORD}")]) {
            docker.withRegistry("${env.REGISTRY}", 'docker-hub-credentials') {
                mysh "docker login -u ${USERNAME} -p ${PASSWORD}"
                app.push(image)
            }
        }
    }

    stage('Clean') {
        sh "docker rmi $image"
    }
}

def mysh(cmd) {
    sh('#!/bin/sh -e\n' + cmd)
}

def copyFilesToWorkSpace() {
    mysh "cp -r /github/workspace/* $WORKSPACE"
}
