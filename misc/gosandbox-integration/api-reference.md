# API Reference

## Table of Contents

- [Session Manager API](#session-manager-api)
- [gosandbox Core API](#gosandbox-core-api)
- [Cloud Integration API](#cloud-integration-api)
- [kubelingo Extensions API](#kubelingo-extensions-api)
- [Monitoring API](#monitoring-api)
- [Configuration API](#configuration-api)

## Session Manager API

### CKADStudySession Class

The main orchestrator for CKAD study sessions with cloud resources.

#### Constructor

```python
CKADStudySession(session_id: str = None, config: SessionConfig = None)
```

**Parameters:**
- `session_id` (optional): Unique identifier for the session. Auto-generated if not provided.
- `config` (optional): Custom session configuration. Uses defaults if not provided.

**Example:**
```python
from tools.session_manager import CKADStudySession

# Create with auto-generated ID
session = CKADStudySession()

# Create with custom ID
session = CKADStudySession("my-study-session-001")

# Create with custom configuration
config = SessionConfig(node_count=3, instance_type="t3.large")
session = CKADStudySession(config=config)
```

#### Methods

##### `initialize_session()`

Initializes a complete CKAD study environment including AWS credentials, EKS cluster, and practice workloads.

```python
def initialize_session() -> None
```

**Raises:**
- `CredentialError`: If AWS credential acquisition fails
- `ClusterError`: If EKS cluster creation fails
- `ConfigurationError`: If environment setup fails

**Example:**
```python
try:
    session.initialize_session()
    print(f"Session {session.session_id} ready for study!")
except Exception as e:
    print(f"Session initialization failed: {e}")
```

##### `get_status()`

Returns current session status and metrics.

```python
def get_status() -> Dict[str, Any]
```

**Returns:**
```python
{
    "session_id": "ckad-20231201-143022",
    "status": "active",
    "start_time": "2023-12-01T14:30:22Z",
    "expires_at": "2023-12-01T18:30:22Z",
    "time_remaining": "3h 45m",
    "cluster_name": "ckad-20231201-143022",
    "cluster_status": "ACTIVE",
    "node_count": 2,
    "pod_count": 12,
    "aws_costs": 0.00,
    "exercises_completed": 5,
    "exercises_total": 20
}
```

##### `extend_session()`

Attempts to extend the session duration (limited by ACG sandbox constraints).

```python
def extend_session(minutes: int = 30) -> bool
```

**Parameters:**
- `minutes`: Number of minutes to extend the session

**Returns:**
- `bool`: True if extension successful, False otherwise

**Example:**
```python
if session.extend_session(30):
    print("Session extended by 30 minutes")
else:
    print("Unable to extend session")
```

##### `cleanup_session()`

Cleans up all cloud resources and terminates the session.

```python
def cleanup_session() -> None
```

**Example:**
```python
session.cleanup_session()
print("All resources cleaned up")
```

##### `start_kubelingo()`

Launches kubelingo with cloud-specific exercises.

```python
def start_kubelingo(exercise_filter: str = None) -> None
```

**Parameters:**
- `exercise_filter` (optional): Filter exercises by category or difficulty

**Example:**
```python
# Start with all exercises
session.start_kubelingo()

# Start with specific category
session.start_kubelingo("AWS Storage")
```

### SessionConfig Class

Configuration object for customizing study sessions.

```python
class SessionConfig:
    def __init__(
        self,
        session_duration: timedelta = timedelta(hours=4),
        cluster_config: Dict[str, Any] = None,
        namespaces: List[str] = None,
        monitoring_enabled: bool = True,
        auto_cleanup: bool = True
    )
```

**Example:**
```python
config = SessionConfig(
    session_duration=timedelta(hours=3),
    cluster_config={
        'node_type': 't3.large',
        'node_count': 3,
        'region': 'us-east-1'
    },
    namespaces=['ckad-practice', 'web-tier', 'data-tier'],
    monitoring_enabled=True
)
```

## gosandbox Core API

### ACloudProvider Class

Handles A Cloud Guru authentication and AWS credential acquisition.

#### Methods

##### `Login()`

Authenticates with A Cloud Guru and acquires AWS sandbox credentials.

```go
func (p *ACloudProvider) Login(username, password string) error
```

**Parameters:**
- `username`: A Cloud Guru username
- `password`: A Cloud Guru password

**Returns:**
- `error`: nil if successful, error details if failed

**Example:**
```go
provider := acloud.ACloudProvider{}
err := provider.Login("user@example.com", "password123")
if err != nil {
    log.Fatal("Login failed:", err)
}
```

##### `GetCredentials()`

Retrieves current AWS sandbox credentials.

```go
func (p *ACloudProvider) GetCredentials() SandboxCredential
```

**Returns:**
```go
type SandboxCredential struct {
    AccessKeyID     string    `json:"aws_access_key_id"`
    SecretAccessKey string    `json:"aws_secret_access_key"`
    SessionToken    string    `json:"aws_session_token"`
    Region          string    `json:"aws_default_region"`
    ExpiresAt       time.Time `json:"expires_at"`
}
```

##### `ExportAWSCredentials()`

Exports credentials to AWS CLI configuration format.

```go
func (p *ACloudProvider) ExportAWSCredentials() error
```

**Example:**
```go
err := provider.ExportAWSCredentials()
if err != nil {
    log.Printf("Failed to export credentials: %v", err)
}
```

### Browser Automation

#### Connection Struct

Manages browser automation for credential acquisition.

```go
type Connection struct {
    Browser *rod.Browser
    Page    *rod.Page
    Url     string
}
```

##### `Login()`

Performs automated login to A Cloud Guru.

```go
func Login(login WebsiteLogin) (Connection, error)
```

**Parameters:**
```go
type WebsiteLogin struct {
    Url      string
    Username string
    Password string
}
```

## Cloud Integration API

### CloudEnvironmentManager Class

Manages cloud-specific Kubernetes operations and exercise generation.

#### Methods

##### `detect_cloud_environment()`

Automatically detects the current cloud environment and cluster type.

```python
def detect_cloud_environment() -> Dict[str, str]
```

**Returns:**
```python
{
    "provider": "aws",
    "cluster_type": "eks",
    "context": "arn:aws:eks:us-west-2:123456789:cluster/ckad-study",
    "region": "us-west-2",
    "cluster_name": "ckad-study"
}
```

##### `load_cloud_specific_exercises()`

Loads exercises tailored to the detected cloud environment.

```python
def load_cloud_specific_exercises() -> List[Dict[str, Any]]
```

**Returns:**
```python
[
    {
        "id": "eks-deployment",
        "category": "AWS Deployment",
        "difficulty": "intermediate",
        "prompt": "Create a Deployment with AWS Load Balancer",
        "starting_yaml": "...",
        "correct_yaml": "...",
        "explanation": "...",
        "cloud_specific": True,
        "estimated_time": 15
    }
]
```

##### `validate_cloud_resources()`

Validates Kubernetes YAML against the cloud environment.

```python
def validate_cloud_resources(yaml_content: str) -> Dict[str, Any]
```

**Parameters:**
- `yaml_content`: YAML manifest to validate

**Returns:**
```python
{
    "valid": True,
    "message": "Resources validated successfully",
    "warnings": ["LoadBalancer may take 2-3 minutes to provision"],
    "cloud_specific": True,
    "estimated_cost": 0.00
}
```

##### `create_eks_cluster()`

Creates an EKS cluster with CKAD-optimized configuration.

```python
def create_eks_cluster(cluster_config: Dict[str, Any]) -> str
```

**Parameters:**
```python
cluster_config = {
    "name": "ckad-study",
    "region": "us-west-2",
    "node_type": "t3.medium",
    "node_count": 2,
    "kubernetes_version": "1.24"
}
```

**Returns:**
- `str`: Cluster ARN if successful

##### `setup_practice_environment()`

Sets up namespaces and practice workloads.

```python
def setup_practice_environment() -> None
```

**Creates:**
- Practice namespaces
- Sample deployments and services
- ConfigMaps and Secrets
- PersistentVolumeClaims
- NetworkPolicies

## kubelingo Extensions API

### Exercise Generation

#### `generate_aws_exercises()`

Generates AWS-specific CKAD exercises.

```python
def generate_aws_exercises() -> List[Exercise]
```

**Returns:**
```python
class Exercise:
    id: str
    category: str
    prompt: str
    starting_yaml: str
    correct_yaml: str
    explanation: str
    difficulty: str
    estimated_time: int
    cloud_specific: bool
    validation_rules: List[str]
```

#### `validate_exercise_solution()`

Validates student solutions against cloud environment.

```python
def validate_exercise_solution(
    exercise_id: str, 
    student_yaml: str
) -> ValidationResult
```

**Returns:**
```python
class ValidationResult:
    correct: bool
    score: float
    feedback: str
    suggestions: List[str]
    cloud_validation: Dict[str, Any]
```

### Quiz Integration

#### `start_cloud_quiz()`

Starts an interactive quiz with cloud-specific questions.

```python
def start_cloud_quiz(
    categories: List[str] = None,
    difficulty: str = None,
    time_limit: int = None
) -> QuizSession
```

**Example:**
```python
quiz = start_cloud_quiz(
    categories=["AWS Storage", "AWS Networking"],
    difficulty="intermediate",
    time_limit=3600  # 1 hour
)
```

## Monitoring API

### ResourceMonitor Class

Monitors cluster resources and session metrics.

#### Methods

##### `collect
</augment_code_snippet>