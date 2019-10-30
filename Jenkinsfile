node {
    def app
    def image

    stage('Clone repository') {
       copyFilesToWorkSpace()
    }

    stage('Build image') {
        image = "${env.REGISTRY}".replace("https://", "") + "/${env.GITHUB_REPOSITORY}:0.0.1"
        app = docker.build(image)
    }

    stage('Push image') {
        docker.withRegistry("${env.REGISTRY}", 'docker-hub-credentials') {
            withCredentials([usernamePassword(credentialsId: 'docker-hub-credentials', usernameVariable: "REGISTRY_USERNAME", passwordVariable: "REGISTRY_PASSWORD")]) {
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
