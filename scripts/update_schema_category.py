#!/usr/bin/env python3
"""
Update the schema_category column for questions in the database based on source_file mapping.
Run this script after restoring the master database to backfill schema_category.
"""
import sqlite3
from kubelingo.utils.config import DATABASE_FILE

def main():
    # Mapping of source file names (suffixes) to schema_category values
    mapping = {
        # Basic/Open-Ended
        'vim_practice.yaml': 'Basic/Open-Ended',
        'kubernetes_with_explanations.yaml': 'Basic/Open-Ended',
        'kubernetes.yaml': 'Basic/Open-Ended',
        'ai_generated_quiz.yaml': 'Basic/Open-Ended',
        'master_quiz_with_explanations.yaml': 'Basic/Open-Ended',
        'core_concepts.yaml': 'Basic/Open-Ended',
        'killercoda_ckad_cheat_sheet.yaml': 'Basic/Open-Ended',
        'pod_design.yaml': 'Basic/Open-Ended',
        'crd.yaml': 'Basic/Open-Ended',
        'helm.yaml': 'Basic/Open-Ended',
        'state.yaml': 'Basic/Open-Ended',
        'multi_container_pods.yaml': 'Basic/Open-Ended',
        'configuration.yaml': 'Basic/Open-Ended',
        'services.yaml': 'Basic/Open-Ended',
        'observability.yaml': 'Basic/Open-Ended',
        'podman.yaml': 'Basic/Open-Ended',
        'ckad_simulator.yaml': 'Basic/Open-Ended',
        'simulator-pods.yaml': 'Basic/Open-Ended',
        'simulator-namespaces.yaml': 'Basic/Open-Ended',
        # Command-Based/Syntax
        'kubectl_operations_quiz.yaml': 'Command-Based/Syntax',
        'kubectl_service_account_operations.yaml': 'Command-Based/Syntax',
        'kubectl_resource_types.yaml': 'Command-Based/Syntax',
        'kubectl_basic_syntax_quiz.yaml': 'Command-Based/Syntax',
        'kubectl_pod_management_quiz.yaml': 'Command-Based/Syntax',
        'kubectl_deployment_management_quiz.yaml': 'Command-Based/Syntax',
        'kubectl_configmap_operations_quiz.yaml': 'Command-Based/Syntax',
        'kubectl_namespace_operations_quiz.yaml': 'Command-Based/Syntax',
        'kubectl_additional_commands_quiz.yaml': 'Command-Based/Syntax',
        'kubectl_secret_management_quiz.yaml': 'Command-Based/Syntax',
        'kubectl_service_account_ops_quiz.yaml': 'Command-Based/Syntax',
        'vim_quiz.yaml': 'Command-Based/Syntax',
        'kubectl_shell_setup_quiz.yaml': 'Command-Based/Syntax',
        'ui_config_footer.yaml': 'Command-Based/Syntax',
        # Manifests
        'yaml_quiz.yaml': 'Manifests',
        'yaml_exercises_quiz.yaml': 'Manifests',
    }

    conn = sqlite3.connect(DATABASE_FILE)
    cursor = conn.cursor()
    print(f"Updating schema_category in database: {DATABASE_FILE}\n")
    for filename, category in mapping.items():
        # Match source_file ending with the filename
        cursor.execute(
            "UPDATE questions SET schema_category = ? WHERE source_file LIKE ?",
            (category, '%' + filename)
        )
        print(f"{cursor.rowcount:4d} rows updated for '{filename}' -> '{category}'")
    conn.commit()
    conn.close()
    print("\nUpdate complete.")

if __name__ == '__main__':
    main()