node {
    def app

    stage('Clone repository') {
       copyFilesToWorkSpace()
    }

    stage('Build image') {
        app = docker.build("${env.GITHUB_REPOSITORY}:0.0.1")
    }

    stage('Push image') {
        /*
        docker.withRegistry('https://registry.hub.docker.com', 'docker-hub-credentials') {
            app.push("${env.BUILD_NUMBER}")
            app.push("latest")
        } */
    }
}

def mysh(cmd) {
    sh('#!/bin/sh -e\n' + cmd)
}

def copyFilesToWorkSpace() {
    mysh "cp -r /github/workspace/* $WORKSPACE"
}
