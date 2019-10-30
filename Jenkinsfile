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

    stage('Registry Login') {
        withCredentials([usernamePassword(credentialsId: 'docker-hub-credentials', usernameVariable: "REGISTRY_USERNAME", passwordVariable: "REGISTRY_PASSWORD")]) {
            mysh "docker login -u $REGISTRY_USERNAME -p $REGISTRY_PASSWORD ${env.REGISTRY}"
        }
    }

    stage('Push image') {
        docker.withRegistry("${env.REGISTRY}", 'docker-hub-credentials') {
            app.push(image)
        }
    }

    stage('Registry Logout') {
        mysh "docker logout ${env.REGISTRY}"
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
