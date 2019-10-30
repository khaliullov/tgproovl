properties([
    parameters([
        credentials(name: 'creds_param', defaultValue: 'registry',
                    credentialType: 'com.cloudbees.plugins.credentials.impl.UsernamePasswordCredentialsImpl',
                    description: '')
    ])
])

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
        withCredentials([usernamePassword(credentialsId: '${creds_param}',
                         usernameVariable: "REGISTRY_USERNAME",
                         passwordVariable: "REGISTRY_PASSWORD")]) {
            mysh "docker login -u $REGISTRY_USERNAME -p $REGISTRY_PASSWORD ${env.REGISTRY}"
            docker.withRegistry("${env.REGISTRY}", '${creds_param}') {
                app.push(image)
            }
            mysh "docker logout ${env.REGISTRY}"
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
