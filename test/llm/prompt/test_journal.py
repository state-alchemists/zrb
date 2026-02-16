"""Tests for the journal prompt component."""

import os
import tempfile
from unittest.mock import Mock, patch

import pytest

from zrb.context.shared_context import SharedContext
from zrb.llm.prompt.journal import create_journal_prompt


def test_journal_prompt_with_empty_journal():
    """Test journal prompt when journal directory and index file exist but are empty."""
    with tempfile.TemporaryDirectory() as temp_dir:
        # Create empty journal directory and index file
        journal_dir = os.path.join(temp_dir, "journal")
        os.makedirs(journal_dir)
        index_file = os.path.join(journal_dir, "index.md")
        with open(index_file, "w") as f:
            f.write("")
        
        # Mock CFG to use our temp directory
        with patch("zrb.llm.prompt.journal.CFG") as mock_cfg:
            mock_cfg.LLM_JOURNAL_DIR = journal_dir
            mock_cfg.LLM_JOURNAL_INDEX_FILE = "index.md"
            
            # Create the journal prompt
            journal_prompt = create_journal_prompt()
            
            # Mock next_handler
            next_handler = Mock(return_value="final_prompt")
            
            # Call the journal prompt
            ctx = SharedContext()
            result = journal_prompt(ctx, "initial_prompt", next_handler)
            
            # Verify the result
            assert result == "final_prompt"
            next_handler.assert_called_once()
            
            # Check that the prompt includes journal system info
            call_args = next_handler.call_args[0]
            assert call_args[0] == ctx
            assert "Journal System" in call_args[1]
            assert "Journal Directory" in call_args[1]
            assert "Index File" in call_args[1]
            assert "AGENTS.md" in call_args[1]


def test_journal_prompt_with_journal_content():
    """Test journal prompt when journal has content."""
    with tempfile.TemporaryDirectory() as temp_dir:
        # Create journal directory with content
        journal_dir = os.path.join(temp_dir, "journal")
        os.makedirs(journal_dir)
        index_file = os.path.join(journal_dir, "index.md")
        journal_content = "# Test Journal\n\nThis is test journal content."
        with open(index_file, "w") as f:
            f.write(journal_content)
        
        # Mock CFG to use our temp directory
        with patch("zrb.llm.prompt.journal.CFG") as mock_cfg:
            mock_cfg.LLM_JOURNAL_DIR = journal_dir
            mock_cfg.LLM_JOURNAL_INDEX_FILE = "index.md"
            
            # Create the journal prompt
            journal_prompt = create_journal_prompt()
            
            # Mock next_handler
            next_handler = Mock(return_value="final_prompt")
            
            # Call the journal prompt
            ctx = SharedContext()
            result = journal_prompt(ctx, "initial_prompt", next_handler)
            
            # Verify the result
            assert result == "final_prompt"
            next_handler.assert_called_once()
            
            # Check that the prompt includes journal content
            call_args = next_handler.call_args[0]
            assert call_args[0] == ctx
            assert "Journal & Notes" in call_args[1]
            assert "Test Journal" in call_args[1]
            assert "This is test journal content" in call_args[1]
            assert "Journal System" in call_args[1]


def test_journal_prompt_creates_missing_directory():
    """Test journal prompt creates missing journal directory."""
    with tempfile.TemporaryDirectory() as temp_dir:
        # Journal directory doesn't exist yet
        journal_dir = os.path.join(temp_dir, "non_existent_journal")
        index_file = os.path.join(journal_dir, "index.md")
        
        # Mock CFG to use our temp directory
        with patch("zrb.llm.prompt.journal.CFG") as mock_cfg:
            mock_cfg.LLM_JOURNAL_DIR = journal_dir
            mock_cfg.LLM_JOURNAL_INDEX_FILE = "index.md"
            
            # Create the journal prompt
            journal_prompt = create_journal_prompt()
            
            # Mock next_handler
            next_handler = Mock(return_value="final_prompt")
            
            # Call the journal prompt
            ctx = SharedContext()
            result = journal_prompt(ctx, "initial_prompt", next_handler)
            
            # Verify the directory was created
            assert os.path.isdir(journal_dir)
            assert os.path.isfile(index_file)
            
            # Verify the result
            assert result == "final_prompt"
            next_handler.assert_called_once()


def test_journal_prompt_creates_missing_index_file():
    """Test journal prompt creates missing index file."""
    with tempfile.TemporaryDirectory() as temp_dir:
        # Journal directory exists but index file doesn't
        journal_dir = os.path.join(temp_dir, "journal")
        os.makedirs(journal_dir)
        index_file = os.path.join(journal_dir, "index.md")
        
        # Mock CFG to use our temp directory
        with patch("zrb.llm.prompt.journal.CFG") as mock_cfg:
            mock_cfg.LLM_JOURNAL_DIR = journal_dir
            mock_cfg.LLM_JOURNAL_INDEX_FILE = "index.md"
            
            # Create the journal prompt
            journal_prompt = create_journal_prompt()
            
            # Mock next_handler
            next_handler = Mock(return_value="final_prompt")
            
            # Call the journal prompt
            ctx = SharedContext()
            result = journal_prompt(ctx, "initial_prompt", next_handler)
            
            # Verify the index file was created
            assert os.path.isfile(index_file)
            
            # Verify the result
            assert result == "final_prompt"
            next_handler.assert_called_once()


def test_journal_prompt_with_custom_index_filename():
    """Test journal prompt with custom index filename."""
    with tempfile.TemporaryDirectory() as temp_dir:
        # Create journal directory with custom index filename
        journal_dir = os.path.join(temp_dir, "journal")
        os.makedirs(journal_dir)
        index_file = os.path.join(journal_dir, "custom_index.md")
        journal_content = "# Custom Journal"
        with open(index_file, "w") as f:
            f.write(journal_content)
        
        # Mock CFG to use our temp directory with custom filename
        with patch("zrb.llm.prompt.journal.CFG") as mock_cfg:
            mock_cfg.LLM_JOURNAL_DIR = journal_dir
            mock_cfg.LLM_JOURNAL_INDEX_FILE = "custom_index.md"
            
            # Create the journal prompt
            journal_prompt = create_journal_prompt()
            
            # Mock next_handler
            next_handler = Mock(return_value="final_prompt")
            
            # Call the journal prompt
            ctx = SharedContext()
            result = journal_prompt(ctx, "initial_prompt", next_handler)
            
            # Verify the result
            assert result == "final_prompt"
            next_handler.assert_called_once()
            
            # Check that the prompt includes custom filename
            call_args = next_handler.call_args[0]
            assert call_args[0] == ctx
            assert "custom_index.md" in call_args[1]
            assert "Custom Journal" in call_args[1]


def test_journal_prompt_edge_case_no_sections():
    """Test the theoretical edge case where no sections are added (should not happen in practice)."""
    # This test mocks the internal behavior to test the fallback path
    with tempfile.TemporaryDirectory() as temp_dir:
        # Create journal directory
        journal_dir = os.path.join(temp_dir, "journal")
        os.makedirs(journal_dir)
        index_file = os.path.join(journal_dir, "index.md")
        with open(index_file, "w") as f:
            f.write("")
        
        # Mock CFG to use our temp directory
        with patch("zrb.llm.prompt.journal.CFG") as mock_cfg:
            mock_cfg.LLM_JOURNAL_DIR = journal_dir
            mock_cfg.LLM_JOURNAL_INDEX_FILE = "index.md"
            
            # Create the journal prompt
            journal_prompt = create_journal_prompt()
            
            # Mock next_handler
            next_handler = Mock(return_value="final_prompt")
            
            # We need to patch make_markdown_section to return None or empty string
            # to simulate the edge case where no sections are created
            with patch("zrb.llm.prompt.journal.make_markdown_section") as mock_make_section:
                # Make it return empty string for both calls
                mock_make_section.return_value = ""
                
                # Call the journal prompt
                ctx = SharedContext()
                result = journal_prompt(ctx, "initial_prompt", next_handler)
                
                # Verify the result - should still call next_handler
                assert result == "final_prompt"
                next_handler.assert_called_once()
                
                # Check that it called next_handler with the original prompt
                call_args = next_handler.call_args[0]
                assert call_args[0] == ctx
                # In this edge case, it should just pass through the current prompt
                # without adding anything (but may add newline due to empty string in sections)
                # The actual behavior is that sections = [""] which is truthy, so it adds newlines
                assert call_args[1] == "initial_prompt\n\n"