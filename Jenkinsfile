node {
    def app
    def image

    stage('Clone repository') {
       copyFilesToWorkSpace()
    }

    stage('Build image') {
        def currentVersion = sh(returnStdout: true,
                                script: 'sed -n -e "/^__version__/p" tgproovl/__init__.py | cut -d\\" -f2').trim()
        image = "${env.REGISTRY}".replace("https://", "") + "/${env.GITHUB_REPOSITORY}:$currentVersion"
        app = docker.build(image)
    }

    stage('Push image') {
        mysh "docker login -u ${env.REGISTRY_USERNAME} -p ${env.REGISTRY_PASSWORD} ${env.REGISTRY}"
        mysh "docker push $image"
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
