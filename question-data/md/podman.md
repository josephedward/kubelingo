# Define, build and modify container images

- Note: The topic is part of the new CKAD syllabus. Here are a few examples of using **podman** to manage the life cycle of container images. The use of **docker** had been the industry standard for many years, but now large companies like [Red Hat](https://www.redhat.com/en/blog/say-hello-buildah-podman-and-skopeo) are moving to a new suite of open source tools: podman, skopeo and buildah. Also Kubernetes has moved in this [direction](https://kubernetes.io/blog/2022/02/17/dockershim-faq/). In particular, `podman` is meant to be the replacement of the `docker` command: so it makes sense to get familiar with it, although they are quite interchangeable considering that they use the same syntax.

## Podman basics

### Create a Dockerfile to deploy an Apache HTTP Server which hosts a custom main page

<details><summary>show</summary>
<p>

```Dockerfile
FROM docker.io/httpd:2.4
RUN echo "Hello, World!" > /usr/local/apache2/htdocs/index.html
```

</p>
</details>

### Build the Dockerfile designed to deploy an Apache HTTP Server with a custom main page and determine how many layers the resulting image consists of.

<details><summary>show</summary>
<p>

```bash
:~$ podman build -t simpleapp .
STEP 1/2: FROM httpd:2.4
STEP 2/2: RUN echo "Hello, World!" > /usr/local/apache2/htdocs/index.html
COMMIT simpleapp
--> ef4b14a72d0
Successfully tagged localhost/simpleapp:latest
ef4b14a72d02ae0577eb0632d084c057777725c279e12ccf5b0c6e4ff5fd598b

:~$ podman images
REPOSITORY               TAG         IMAGE ID      CREATED        SIZE
localhost/simpleapp      latest      ef4b14a72d02  8 seconds ago  148 MB
docker.io/library/httpd  2.4         98f93cd0ec3b  7 days ago     148 MB

:~$ podman image tree localhost/simpleapp:latest
Image ID: ef4b14a72d02
Tags:     [localhost/simpleapp:latest]
Size:     147.8MB
Image Layers
├── ID: ad6562704f37 Size:  83.9MB
├── ID: c234616e1912 Size: 3.072kB
├── ID: c23a797b2d04 Size: 2.721MB
├── ID: ede2e092faf0 Size: 61.11MB
├── ID: 971c2cdf3872 Size: 3.584kB Top Layer of: [docker.io/library/httpd:2.4]
└── ID: 61644e82ef1f Size: 6.144kB Top Layer of: [localhost/simpleapp:latest]
```

</p>
</details>

### Run the Docker image of the Apache HTTP Server with a custom main page locally, inspect its status and logs, and finally test that it responds as expected.

<details><summary>show</summary>
<p>

```bash
:~$ podman run -d --name test -p 8080:80 localhost/simpleapp
2f3d7d613ea6ba19703811d30704d4025123c7302ff6fa295affc9bd30e532f8

:~$ podman ps
CONTAINER ID  IMAGE                       COMMAND           CREATED        STATUS            PORTS                 NAMES
2f3d7d613ea6  localhost/simpleapp:latest  httpd-foreground  5 seconds ago  Up 6 seconds ago  0.0.0.0:8080->80/tcp  test

:~$ podman logs test
AH00558: httpd: Could not reliably determine the server's fully qualified domain name, using 10.0.2.100. Set the 'ServerName' directive globally to suppress this message
AH00558: httpd: Could not reliably determine the server's fully qualified domain name, using 10.0.2.100. Set the 'ServerName' directive globally to suppress this message
[Sat Jun 04 16:15:38.071377 2022] [mpm_event:notice] [pid 1:tid 139756978220352] AH00489: Apache/2.4.53 (Unix) configured -- resuming normal operations
[Sat Jun 04 16:15:38.073570 2022] [core:notice] [pid 1:tid 139756978220352] AH00094: Command line: 'httpd -D FOREGROUND'

:~$ curl 0.0.0.0:8080
Hello, World!
```

</p>
</details>

### After running the Docker image of the Apache HTTP Server with a custom main page locally, inspecting its status and logs, and finally testing that it responds as expected, run a command inside the pod to print out the index.html file.

<details><summary>show</summary>
<p>

```bash
:~$ podman exec -it test cat /usr/local/apache2/htdocs/index.html
Hello, World!
```
</p>
</details>

### After successfully running the Docker image of the Apache HTTP Server with a custom main page locally, inspecting its status and logs, and verifying that it responds as expected by running a command inside the pod to print out the index.html file, tag the same image with the IP address and port of a private local registry and then push the image to this registry.

<details><summary>show</summary>
<p>

> Note: Some small distributions of Kubernetes (such as [microk8s](https://microk8s.io/docs/registry-built-in)) have a built-in registry you can use for this exercise. If this is not your case, you'll have to setup it on your own.

```bash
:~$ podman tag localhost/simpleapp $registry_ip:5000/simpleapp

:~$ podman push $registry_ip:5000/simpleapp
```

</p>
</details>

 Verify that the registry contains the pushed image and that you can pull it

<details><summary>show</summary>
<p>

```bash
:~$ curl http://$registry_ip:5000/v2/_catalog
{"repositories":["simpleapp"]}

# remove the image already present
:~$ podman rmi $registry_ip:5000/simpleapp

:~$ podman pull $registry_ip:5000/simpleapp
Trying to pull 10.152.183.13:5000/simpleapp:latest...
Getting image source signatures
Copying blob 643ea8c2c185 skipped: already exists
Copying blob 972107ece720 skipped: already exists
Copying blob 9857eeea6120 skipped: already exists
Copying blob 93859aa62dbd skipped: already exists
Copying blob 8e47efbf2b7e skipped: already exists
Copying blob 42e0f5a91e40 skipped: already exists
Copying config ef4b14a72d done
Writing manifest to image destination
Storing signatures
ef4b14a72d02ae0577eb0632d084c057777725c279e12ccf5b0c6e4ff5fd598b
```

</p>
</details>

### After successfully tagging and pushing the Docker image of the Apache HTTP Server to a private local registry as previously outlined, create a container from this image without running/starting it.

<details><summary>show</summary>
<p>

```bash
:~$ podman create busybox # create
Resolved "busybox" as an alias (/etc/containers/registries.conf.d/000-shortnames.conf)
Trying to pull docker.io/library/busybox:latest...
Getting image source signatures
Copying blob sha256:213a27df5921cd9ae24732504c590bb6408911c20fb50a597f2a40896d554a8f
Copying config sha256:3fba0c87fcc8ba126bf99e4ee205b43c91ffc6b15bb052315312e71bc6296551
Writing manifest to image destination
51b613406e8889213c176523e1c430e4bd00047965b0c22cff5b1c9badfbc452

:~$ podman container ls -a
CONTAINER ID  IMAGE                             COMMAND     CREATED        STATUS      PORTS       NAMES
51b613406e88  docker.io/library/busybox:latest  sh          2 minutes ago  Created                 adoring_almeida
```

</p>
</details>

### Export the container created from the Docker image of the Apache HTTP Server that was tagged and pushed to a private local registry, without starting it, to an output.tar file.

<details><summary>show</summary>
<p>

```bash
:~$ podman container ls -a # pick the container id
CONTAINER ID  IMAGE                             COMMAND     CREATED        STATUS      PORTS       NAMES
51b613406e88  docker.io/library/busybox:latest  sh          2 minutes ago  Created                 adoring_almeida

:~$ podman export <container id> --output=output.tar

:~$ ls -al output.tar
-rw-r--r--@ 1 limistah  wheel  4272640 28 Aug 13:48 output.tar
```

</p>
</details>

### Run a pod with the Apache HTTP Server image that was previously tagged and pushed to a private local registry.

<details><summary>show</summary>
<p>

```bash
:~$ kubectl run simpleapp --image=$registry_ip:5000/simpleapp --port=80

:~$ curl ${kubectl get pods simpleapp -o jsonpath='{.status.podIP}'}
Hello, World!
```

</p>
</details>

### After running a pod with the Apache HTTP Server image from a private local registry, log into a remote registry server and then read the credentials from the default file.

<details><summary>show</summary>
<p>

> Note: The two most used container registry servers with a free plan are [DockerHub](https://hub.docker.com/) and [Quay.io](https://quay.io/).

```bash
:~$ podman login --username $YOUR_USER --password $YOUR_PWD docker.io
:~$ cat ${XDG_RUNTIME_DIR}/containers/auth.json
{
        "auths": {
                "docker.io": {
                        "auth": "Z2l1bGl0JLSGtvbkxCcX1xb617251xh0x3zaUd4QW45Q3JuV3RDOTc="
                }
        }
}
```

</p>
</details>

### Create a Kubernetes secret to store the login credentials for a remote registry server, after logging in to access an Apache HTTP Server image from a private local registry, using both the credentials retrieved from the default file and directly from the command line interface (CLI).

<details><summary>show</summary>
<p>

```bash
:~$ kubectl create secret generic mysecret --from-file=.dockerconfigjson=${XDG_RUNTIME_DIR}/containers/auth.json --type=kubernetes.io/dockeconfigjson
secret/mysecret created
:~$ kubectl create secret docker-registry mysecret2 --docker-server=https://index.docker.io/v1/ --docker-username=$YOUR_USR --docker-password=$YOUR_PWD
secret/mysecret2 created
```

</p>
</details>

### Create the manifest for a Pod that uses one of the two secrets created for storing login credentials for a remote registry server, to pull an Apache HTTP Server image hosted on the same private local registry, where the secrets were either retrieved from the default file or directly from the command line interface (CLI).

<details><summary>show</summary>
<p>

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: private-reg
spec:
  containers:
  - name: private-reg-container
    image: $YOUR_PRIVATE_IMAGE
  imagePullSecrets:
  - name: mysecret
```

</p>
</details>

### Following the creation of a Pod manifest that utilizes one of the two secrets for storing login credentials to pull an Apache HTTP Server image from a private local registry, describe the process for cleaning up all the images and containers associated with this setup.

<details><summary>show</summary>
<p>

```bash
:~$ podman rm --all --force
:~$ podman rmi --all
:~$ kubectl delete pod simpleapp
```

</p>
</details>
