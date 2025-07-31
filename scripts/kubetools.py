#!/usr/bin/env python3
"""
kubetools: consolidated CLI for Kubelingo helper scripts.

Usage:
  kubetools organize [--dry-run]
  kubetools enrich SRC_DIR DEST_FILE [--format json|yaml] [--model MODEL] [--dry-run] [--generate-validations]
  kubetools static-validate IN_PATH [--overwrite]
  kubetools gen-manifests
  kubetools gen-kubectl-ops
  kubetools gen-resource-ref
  kubetools ckad [export|import|normalize] [options]
"""
import argparse
import subprocess
import sys
from pathlib import Path

def run_script(script_name, args):
    """Helper to run a script in the scripts directory."""
    script = Path(__file__).parent / script_name
    if not script.exists():
        print(f"Error: script {script_name} not found", file=sys.stderr)
        sys.exit(1)
    cmd = [sys.executable, str(script)] + args
    return subprocess.run(cmd).returncode

def main():
    parser = argparse.ArgumentParser(prog='kubetools', description='Unified Kubelingo helper')
    sub = parser.add_subparsers(dest='cmd', required=True)

    # organize
    p = sub.add_parser('organize', help='Organize question-data files')
    p.add_argument('--dry-run', action='store_true', help='Dry run file organization')

    # enrich
    p = sub.add_parser('enrich', help='Deduplicate and AI-enrich question-data')
    p.add_argument('src_dir', help='Source directory for question-data')
    p.add_argument('dest_file', help='Destination file for enriched data')
    p.add_argument('--format', choices=['json','yaml'], default='json', help='Output format')
    p.add_argument('--model', default='gpt-3.5-turbo', help='AI model to use')
    p.add_argument('--dry-run', action='store_true', help='Dry run enrichment')
    p.add_argument('--generate-validations', action='store_true', help='Also generate validation_steps via AI')

    # static-validate
    p = sub.add_parser('static-validate', help='Generate validation_steps from answer YAML statically')
    p.add_argument('in_path', help='JSON file or directory to process')
    p.add_argument('--overwrite', action='store_true', help='Overwrite original files')

    # gen-manifests
    sub.add_parser('gen-manifests', help='Generate quiz manifests and solution files from question-data')

    # gen-kubectl-ops
    sub.add_parser('gen-kubectl-ops', help='Generate kubectl operations quiz manifest')

    # gen-resource-ref
    sub.add_parser('gen-resource-ref', help='Generate resource reference quiz manifest')

    # ckad
    p = sub.add_parser('ckad', help='CKAD spec management tool')
    p.add_argument('subcmd', choices=['export','import','normalize'], help='CKAD subcommand')
    # export/import flags
    p.add_argument('--csv', help='Input or output CSV path')
    p.add_argument('--json', help='Input or output JSON path')
    p.add_argument('--yaml', help='Input or output YAML path')

    args, _ = parser.parse_known_args()

    if args.cmd == 'organize':
        sys.exit(run_script('organize_question_data.py', ['--dry-run'] if args.dry_run else []))
    if args.cmd == 'enrich':
        cmd_args = [args.src_dir, args.dest_file]
        if args.dry_run: cmd_args.append('--dry-run')
        if args.generate_validations: cmd_args.append('--generate-validations')
        cmd_args += ['--model', args.model, '--format', args.format]
        sys.exit(run_script('enrich_and_dedup_questions.py', cmd_args))
    if args.cmd == 'static-validate':
        cmd_args = [args.in_path]
        if args.overwrite: cmd_args.append('--overwrite')
        sys.exit(run_script('generate_validation_steps.py', cmd_args))
    if args.cmd == 'gen-manifests':
        sys.exit(run_script('generate_manifests.py', []))
    if args.cmd == 'gen-kubectl-ops':
        sys.exit(run_script('generate_kubectl_operations_quiz.py', []))
    if args.cmd == 'gen-resource-ref':
        sys.exit(run_script('generate_resource_reference_quiz.py', []))
    if args.cmd == 'ckad':
        ckad_args = [args.subcmd]
        if args.subcmd == 'export':
            if args.csv: ckad_args += ['--csv', args.csv]
            if args.json: ckad_args += ['--json', args.json]
            if args.yaml: ckad_args += ['--yaml', args.yaml]
        elif args.subcmd == 'import':
            if args.json: ckad_args += ['--json', args.json]
            if args.yaml: ckad_args += ['--yaml', args.yaml]
            if args.csv: ckad_args += ['--csv', args.csv]
        elif args.subcmd == 'normalize':
            if args.csv: ckad_args += ['--input', args.csv]
        sys.exit(run_script('ckad.py', ckad_args))

if __name__ == '__main__':
    main()