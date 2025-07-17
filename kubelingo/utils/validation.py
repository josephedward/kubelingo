import re
import yaml
from typing import Dict, Any, List, Optional

def commands_equivalent(cmd1: str, cmd2: str) -> bool:
    """
    Check if two kubectl commands are functionally equivalent.
    This is a simplified version - the Rust implementation would be more comprehensive.
    """
    # Normalize whitespace and remove extra spaces
    cmd1_norm = ' '.join(cmd1.strip().split())
    cmd2_norm = ' '.join(cmd2.strip().split())
    
    # Direct match
    if cmd1_norm == cmd2_norm:
        return True
    
    # Parse kubectl commands for semantic comparison
    return _parse_and_compare_kubectl(cmd1_norm, cmd2_norm)

def _parse_and_compare_kubectl(cmd1: str, cmd2: str) -> bool:
    """Parse and compare kubectl commands semantically."""
    try:
        # Extract command parts
        parts1 = cmd1.split()
        parts2 = cmd2.split()
        
        # Must both be kubectl commands
        if not (parts1[0] == 'kubectl' and parts2[0] == 'kubectl'):
            return cmd1 == cmd2
        
        # Compare main action (get, create, apply, etc.)
        if len(parts1) < 2 or len(parts2) < 2:
            return cmd1 == cmd2
            
        action1 = parts1[1]
        action2 = parts2[1]
        
        if action1 != action2:
            return False
        
        # For simple cases, compare remaining parts
        # This is a simplified implementation
        remaining1 = set(parts1[2:])
        remaining2 = set(parts2[2:])
        
        return remaining1 == remaining2
        
    except Exception:
        # Fall back to string comparison
        return cmd1 == cmd2

def validate_yaml_structure(yaml_content: str, expected_structure: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Validate YAML structure and return validation results.
    """
    result = {
        'valid': False,
        'errors': [],
        'warnings': [],
        'parsed_yaml': None
    }
    
    try:
        # Parse YAML
        parsed = yaml.safe_load(yaml_content)
        result['parsed_yaml'] = parsed
        
        if parsed is None:
            result['errors'].append("YAML content is empty or null")
            return result
        
        # Basic Kubernetes resource validation
        if isinstance(parsed, dict):
            # Check required Kubernetes fields
            required_fields = ['apiVersion', 'kind', 'metadata']
            missing_fields = [field for field in required_fields if field not in parsed]
            
            if missing_fields:
                result['errors'].extend([f"Missing required field: {field}" for field in missing_fields])
            else:
                # Basic structure looks good
                result['valid'] = True
                
                # Additional validations
                if 'metadata' in parsed and 'name' not in parsed.get('metadata', {}):
                    result['warnings'].append("metadata.name is recommended")
        
        # Compare with expected structure if provided
        if expected_structure and result['valid']:
            comparison_result = _compare_yaml_structures(parsed, expected_structure)
            if not comparison_result['matches']:
                result['errors'].extend(comparison_result['differences'])
                result['valid'] = False
        
    except yaml.YAMLError as e:
        result['errors'].append(f"YAML parsing error: {str(e)}")
    except Exception as e:
        result['errors'].append(f"Validation error: {str(e)}")
    
    return result

def _compare_yaml_structures(actual: Dict[str, Any], expected: Dict[str, Any]) -> Dict[str, Any]:
    """Compare two YAML structures and return differences."""
    result = {
        'matches': True,
        'differences': []
    }
    
    def _compare_recursive(actual_val, expected_val, path=""):
        if type(actual_val) != type(expected_val):
            result['differences'].append(f"Type mismatch at {path}: expected {type(expected_val).__name__}, got {type(actual_val).__name__}")
            result['matches'] = False
            return
        
        if isinstance(expected_val, dict):
            for key, value in expected_val.items():
                current_path = f"{path}.{key}" if path else key
                if key not in actual_val:
                    result['differences'].append(f"Missing key: {current_path}")
                    result['matches'] = False
                else:
                    _compare_recursive(actual_val[key], value, current_path)
        
        elif isinstance(expected_val, list):
            if len(actual_val) != len(expected_val):
                result['differences'].append(f"List length mismatch at {path}: expected {len(expected_val)}, got {len(actual_val)}")
                result['matches'] = False
            else:
                for i, (actual_item, expected_item) in enumerate(zip(actual_val, expected_val)):
                    _compare_recursive(actual_item, expected_item, f"{path}[{i}]")
        
        else:
            if actual_val != expected_val:
                result['differences'].append(f"Value mismatch at {path}: expected {expected_val}, got {actual_val}")
                result['matches'] = False
    
    _compare_recursive(actual, expected)
    return result
import re
import yaml
from typing import Dict, Any, List, Optional

def commands_equivalent(cmd1: str, cmd2: str) -> bool:
    """
    Check if two kubectl commands are functionally equivalent.
    This is a simplified version - the Rust implementation would be more comprehensive.
    """
    # Normalize whitespace and remove extra spaces
    cmd1_norm = ' '.join(cmd1.strip().split())
    cmd2_norm = ' '.join(cmd2.strip().split())
    
    # Direct match
    if cmd1_norm == cmd2_norm:
        return True
    
    # Parse kubectl commands for semantic comparison
    return _parse_and_compare_kubectl(cmd1_norm, cmd2_norm)

def _parse_and_compare_kubectl(cmd1: str, cmd2: str) -> bool:
    """Parse and compare kubectl commands semantically."""
    try:
        # Extract command parts
        parts1 = cmd1.split()
        parts2 = cmd2.split()
        
        # Must both be kubectl commands
        if not (parts1[0] == 'kubectl' and parts2[0] == 'kubectl'):
            return cmd1 == cmd2
        
        # Compare main action (get, create, apply, etc.)
        if len(parts1) < 2 or len(parts2) < 2:
            return cmd1 == cmd2
            
        action1 = parts1[1]
        action2 = parts2[1]
        
        if action1 != action2:
            return False
        
        # For simple cases, compare remaining parts
        # This is a simplified implementation
        remaining1 = set(parts1[2:])
        remaining2 = set(parts2[2:])
        
        return remaining1 == remaining2
        
    except Exception:
        # Fall back to string comparison
        return cmd1 == cmd2

def validate_yaml_structure(yaml_content: str, expected_structure: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Validate YAML structure and return validation results.
    """
    result = {
        'valid': False,
        'errors': [],
        'warnings': [],
        'parsed_yaml': None
    }
    
    try:
        # Parse YAML
        parsed = yaml.safe_load(yaml_content)
        result['parsed_yaml'] = parsed
        
        if parsed is None:
            result['errors'].append("YAML content is empty or null")
            return result
        
        # Basic Kubernetes resource validation
        if isinstance(parsed, dict):
            # Check required Kubernetes fields
            required_fields = ['apiVersion', 'kind', 'metadata']
            missing_fields = [field for field in required_fields if field not in parsed]
            
            if missing_fields:
                result['errors'].extend([f"Missing required field: {field}" for field in missing_fields])
            else:
                # Basic structure looks good
                result['valid'] = True
                
                # Additional validations
                if 'metadata' in parsed and 'name' not in parsed.get('metadata', {}):
                    result['warnings'].append("metadata.name is recommended")
        
        # Compare with expected structure if provided
        if expected_structure and result['valid']:
            comparison_result = _compare_yaml_structures(parsed, expected_structure)
            if not comparison_result['matches']:
                result['errors'].extend(comparison_result['differences'])
                result['valid'] = False
        
    except yaml.YAMLError as e:
        result['errors'].append(f"YAML parsing error: {str(e)}")
    except Exception as e:
        result['errors'].append(f"Validation error: {str(e)}")
    
    return result

def _compare_yaml_structures(actual: Dict[str, Any], expected: Dict[str, Any]) -> Dict[str, Any]:
    """Compare two YAML structures and return differences."""
    result = {
        'matches': True,
        'differences': []
    }
    
    def _compare_recursive(actual_val, expected_val, path=""):
        if type(actual_val) != type(expected_val):
            result['differences'].append(f"Type mismatch at {path}: expected {type(expected_val).__name__}, got {type(actual_val).__name__}")
            result['matches'] = False
            return
        
        if isinstance(expected_val, dict):
            for key, value in expected_val.items():
                current_path = f"{path}.{key}" if path else key
                if key not in actual_val:
                    result['differences'].append(f"Missing key: {current_path}")
                    result['matches'] = False
                else:
                    _compare_recursive(actual_val[key], value, current_path)
        
        elif isinstance(expected_val, list):
            if len(actual_val) != len(expected_val):
                result['differences'].append(f"List length mismatch at {path}: expected {len(expected_val)}, got {len(actual_val)}")
                result['matches'] = False
            else:
                for i, (actual_item, expected_item) in enumerate(zip(actual_val, expected_val)):
                    _compare_recursive(actual_item, expected_item, f"{path}[{i}]")
        
        else:
            if actual_val != expected_val:
                result['differences'].append(f"Value mismatch at {path}: expected {expected_val}, got {actual_val}")
                result['matches'] = False
    
    _compare_recursive(actual, expected)
    return result
