use pyo3::prelude::*;
use regex::Regex;

#[pyfunction]
fn commands_equivalent(user_cmd: String, expected_cmd: String) -> bool {
    // Rust implementation of command comparison logic
    let normalize = |cmd: &str| -> String {
        let re = Regex::new(r"\s+").unwrap();
        re.replace_all(cmd.trim(), " ").to_lowercase()
    };
    
    normalize(&user_cmd) == normalize(&expected_cmd)
}

#[pyfunction] 
fn validate_yaml_structure(yaml_content: String) -> PyResult<(bool, String)> {
    // Fast YAML validation in Rust
    match serde_yaml::from_str::<serde_yaml::Value>(&yaml_content) {
        Ok(parsed) => {
            // Check required k8s fields
            if let Some(obj) = parsed.as_mapping() {
                let has_api_version = obj.contains_key("apiVersion");
                let has_kind = obj.contains_key("kind");
                let has_metadata = obj.contains_key("metadata");
                
                if has_api_version && has_kind && has_metadata {
                    Ok((true, "Valid Kubernetes YAML".to_string()))
                } else {
                    Ok((false, "Missing required fields".to_string()))
                }
            } else {
                Ok((false, "Invalid YAML structure".to_string()))
            }
        }
        Err(e) => Ok((false, format!("YAML parse error: {}", e)))
    }
}

#[pymodule]
fn kubelingo_core(_py: Python, m: &PyModule) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(commands_equivalent, m)?)?;
    m.add_function(wrap_pyfunction!(validate_yaml_structure, m)?)?;
    Ok(())
}
use pyo3::prelude::*;

/// A placeholder function.
#[pyfunction]
fn hello() -> &'static str {
    "Hello from Rust!"
}

#[pymodule]
fn _native(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(hello, m)?)?;
    Ok(())
}
