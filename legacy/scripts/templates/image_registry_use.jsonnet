// Jsonnet template for 'image_registry_use' topic
// Generates a simple Pod manifest demonstrating image registry usage
local t = std.extVar("topic");
{
  apiVersion: "v1",
  kind: "Pod",
  metadata: {
    name: std.format("%s-pod", t),
  },
  spec: {
    containers: [
      {
        name: std.format("%s-container", t),
                image: std.format("%s/my-image:latest", std.extVar("registry", "myregistry.com")),
        imagePullPolicy: "IfNotPresent",
      }
    ],
    imagePullSecrets: [
      { name: std.extVar("pullSecret", "my-pull-secret") }
    ],
  },
}