import pytest
from cli import generate_command, question_generator_instance, KubernetesTopics
import cli # Import cli module to patch inquirer

@pytest.mark.parametrize("topic", [t.value for t in KubernetesTopics])
def test_generate_command_no_key_errors(topic, mocker):
    """
    Tests that generate_command does not raise KeyError for any topic.
    It attempts to generate a question and then calls generate_command with its context.
    """
    # Mock inquirer.text().execute() to prevent interactive prompts
    # and provide a dummy input for the user's command.
    mocker.patch('cli.inquirer.text', return_value=mocker.Mock(execute=lambda: "dummy_command"))
    mocker.patch('cli.inquirer.select', return_value=mocker.Mock(execute=lambda: topic)) # Mock topic selection

    # Generate a question for the given topic
    # We set include_context=True to ensure context_variables are populated
    q = question_generator_instance.generate_question(topic=topic, include_context=True)
    
    # Extract context variables, defaulting to an empty dict if none are present
    context_vars = q.get('context_variables', {})

    # Call generate_command with the generated context variables
    # We expect no KeyError to be raised
    try:
        # Pass the topic directly to generate_command to bypass interactive topic selection
        # and pass the question_generator_instance for consistency.
        generate_command(topic=topic, gen=question_generator_instance)
    except KeyError as e:
        pytest.fail(f"KeyError encountered for topic '{topic}': {e}")
    except Exception as e:
        pytest.fail(f"Unexpected error encountered for topic '{topic}': {e}")