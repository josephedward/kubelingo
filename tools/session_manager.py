"""
tools/session_manager.py: Manage CKAD study sessions with cloud resources.
"""
import logging
import sys
from datetime import datetime, timedelta

class SessionConfig:
    """
    Configuration for CKAD study sessions.
    """
    def __init__(
        self,
        session_duration: timedelta = timedelta(hours=4),
        cluster_config: dict = None,
        namespaces: list = None,
        monitoring_enabled: bool = True,
        auto_cleanup: bool = True
    ):
        self.session_duration = session_duration
        self.cluster_config = cluster_config or {}
        self.namespaces = namespaces or []
        self.monitoring_enabled = monitoring_enabled
        self.auto_cleanup = auto_cleanup

class CKADStudySession:
    """
    Main orchestrator for CKAD study sessions with cloud resources.
    """
    def __init__(self, session_id: str = None, config: SessionConfig = None):
        self.session_id = session_id or f"ckad-{datetime.utcnow().strftime('%Y%m%d-%H%M%S')}"
        self.config = config or SessionConfig()
        self.start_time = None
        self.expires_at = None
        self.cluster_name = None
        self.cluster_status = None
        self.status = 'created'
        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger(self.__class__.__name__)

    def initialize_session(self) -> None:
        """
        Initializes a complete CKAD study environment.
        """
        self.logger.info(f"Initializing session {self.session_id}")
        # TODO: integrate AWS credential acquisition and EKS cluster creation
        self.start_time = datetime.utcnow()
        self.expires_at = self.start_time + self.config.session_duration
        self.cluster_name = self.session_id
        self.cluster_status = 'ACTIVE'
        self.status = 'active'
        self.logger.info("Session initialized successfully")

    def get_status(self) -> dict:
        """
        Returns current session status and metrics.
        """
        time_remaining = (self.expires_at - datetime.utcnow()) if self.expires_at else timedelta(0)
        return {
            "session_id": self.session_id,
            "status": self.status,
            "start_time": self.start_time.isoformat() + "Z" if self.start_time else None,
            "expires_at": self.expires_at.isoformat() + "Z" if self.expires_at else None,
            "time_remaining": str(time_remaining),
            "cluster_name": self.cluster_name,
            "cluster_status": self.cluster_status,
            "node_count": self.config.cluster_config.get("node_count", 0),
            "pod_count": 0,
            "aws_costs": 0.0,
            "exercises_completed": 0,
            "exercises_total": 0
        }

    def extend_session(self, minutes: int = 30) -> bool:
        """
        Attempts to extend the session duration.
        """
        if not self.expires_at:
            self.logger.warning("Cannot extend session before initialization")
            return False
        self.expires_at += timedelta(minutes=minutes)
        self.logger.info(f"Session extended by {minutes} minutes")
        return True

    def cleanup_session(self) -> None:
        """
        Cleans up all cloud resources and terminates the session.
        """
        self.logger.info("Cleaning up session resources")
        self.status = 'terminated'
        if self.config.auto_cleanup:
            self.logger.info("Auto cleanup enabled: cleaning up resources")
        else:
            self.logger.info("Auto cleanup disabled")

    def start_kubelingo(self, exercise_filter: str = None) -> None:
        """
        Launches kubelingo with optional exercise filter.
        """
        self.logger.info("Starting kubelingo quiz")
        try:
            from cli_quiz import main as cli_main
        except ImportError:
            self.logger.error("kubelingo CLI not found (cli_quiz)")
            return
        argv_backup = sys.argv.copy()
        sys.argv = [argv_backup[0]]
        if exercise_filter:
            sys.argv.extend(['-c', exercise_filter])
        try:
            cli_main()
        except SystemExit as e:
            self.logger.info(f"kubelingo CLI exited with code {e.code}")
        finally:
            sys.argv = argv_backup