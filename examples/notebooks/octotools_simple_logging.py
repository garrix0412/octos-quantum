#!/usr/bin/env python3
"""
OctoTools Solver with Simple Logging

A simplified script that combines environment setup, solver construction,
and query execution with basic logging functionality.

Usage:
    python octotools_simple_logging.py
"""

import os
import sys
import logging
import traceback
from datetime import datetime
from contextlib import contextmanager

# Third-party imports
import dotenv

# OctoTools imports
from octotools.solver import construct_solver


class TeeOutput:
    """Redirect stdout/stderr to both file and original stream."""
    
    def __init__(self, log_file, original_stream, prefix="STDOUT"):
        self.log_file = log_file
        self.original_stream = original_stream
        self.prefix = prefix
        self.logger = logging.getLogger(__name__)
    
    def write(self, text):
        """Write text to both log file and original stream."""
        if text and text.strip():
            # Write to original stream (console)
            self.original_stream.write(text)
            self.original_stream.flush()
            
            # Write to log with timestamp and prefix
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S,%f")[:-3]
            log_entry = f"{timestamp} | {self.prefix} | {text.rstrip()}\n"
            self.log_file.write(log_entry)
            self.log_file.flush()
    
    def flush(self):
        """Flush both streams."""
        self.original_stream.flush()
        self.log_file.flush()


@contextmanager
def capture_output(log_file):
    """Context manager to capture stdout and stderr."""
    # Store original streams
    original_stdout = sys.stdout
    original_stderr = sys.stderr
    
    try:
        # Create Tee objects
        tee_stdout = TeeOutput(log_file, original_stdout, "STDOUT")
        tee_stderr = TeeOutput(log_file, original_stderr, "STDERR")
        
        # Redirect streams
        sys.stdout = tee_stdout
        sys.stderr = tee_stderr
        
        yield
        
    finally:
        # Restore original streams
        sys.stdout = original_stdout
        sys.stderr = original_stderr


def setup_logging():
    """Setup simple logging to both file and console."""
    # Create timestamp for log file
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = f"octotools_log_{timestamp}.log"
    
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s | %(levelname)s | %(message)s',
        handlers=[
            logging.FileHandler(log_file, encoding='utf-8'),
            logging.StreamHandler(sys.stdout)
        ]
    )
    
    logger = logging.getLogger(__name__)
    logger.info(f"Logging started - Log file: {log_file}")
    return logger, log_file


def load_environment(logger):
    """Load environment variables from .env file."""
    try:
        # Try loading from current directory and parent directories
        env_files = ['.env', '../.env', '../../.env']
        for env_file in env_files:
            if os.path.exists(env_file):
                dotenv.load_dotenv(env_file)
                logger.info(f"Environment loaded from: {env_file}")
                break
        else:
            dotenv.load_dotenv()  # Try default loading
            logger.info("Environment variables loaded (default)")
        
        # Check API key
        if os.getenv('OPENAI_API_KEY'):
            logger.info("OPENAI_API_KEY found")
        else:
            logger.warning("OPENAI_API_KEY not found - may cause errors")
            
    except Exception as e:
        logger.error(f"Failed to load environment: {e}")


def main():
    """Main execution function."""
    
    # Setup logging
    logger, log_filename = setup_logging()
    start_time = datetime.now()
    
    try:
        logger.info("=== OctoTools Execution Started ===")
        
        # Load environment
        logger.info("Loading environment variables...")
        load_environment(logger)
        
        # Configure solver
        logger.info("Configuring solver...")
        solver_config = {
            "llm_engine_name": "gpt-4o-mini",
            "enabled_tools": ["all"],
            "output_types": "final,direct",
            "max_steps": 10,
            "max_time": 50,
            "max_completion_tokens": 4000,
            "root_cache_dir": "solver_cache",
            "verbose": True
        }
        
        for key, value in solver_config.items():
            logger.info(f"  {key}: {value}")
        
        # Construct solver with output capture
        logger.info("Constructing solver...")
        with open(log_filename, 'a', encoding='utf-8') as log_file:
            with capture_output(log_file):
                solver = construct_solver(**solver_config)
        logger.info("Solver constructed successfully")
        
        # Execute query with output capture
        query = "Solve for the ground state energy of 8 qubits TFIM problems."
        logger.info(f"Executing query: {query}")
        
        query_start = datetime.now()
        with open(log_filename, 'a', encoding='utf-8') as log_file:
            with capture_output(log_file):
                output = solver.solve(question=query)
        query_end = datetime.now()
        
        query_time = (query_end - query_start).total_seconds()
        logger.info(f"Query completed in {query_time:.2f} seconds")
        
        # Log results summary
        if isinstance(output, dict):
            logger.info("Results summary:")
            if "final_output" in output:
                logger.info("  - Final output: Available")
            if "direct_output" in output:
                logger.info("  - Direct output: Available")
            if "step_count" in output:
                logger.info(f"  - Steps executed: {output['step_count']}")
            if "memory" in output:
                logger.info(f"  - Memory actions: {len(output['memory'])}")
        
        # Calculate total time
        end_time = datetime.now()
        total_time = (end_time - start_time).total_seconds()
        
        logger.info(f"=== Execution Completed Successfully in {total_time:.2f} seconds ===")
        
    except Exception as e:
        # Log error details
        logger.error(f"Execution failed: {type(e).__name__}: {str(e)}")
        logger.error(f"Traceback:\n{traceback.format_exc()}")
        
        end_time = datetime.now()
        total_time = (end_time - start_time).total_seconds()
        logger.error(f"=== Execution Failed after {total_time:.2f} seconds ===")
        
        # Re-raise the exception if needed
        # raise


if __name__ == "__main__":
    main()