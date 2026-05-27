from src.domain.audit import AuditAction, AuditLogger


def test_audit_action_values() -> None:
    assert AuditAction.BOT_START == "bot_start"
    assert AuditAction.INSTALL_PROTOCOL == "install_protocol"
    assert AuditAction.CREATE_CLIENT == "create_client"
    assert AuditAction.DELETE_CLIENT == "delete_client"
    assert AuditAction.GET_LINK == "get_link"
    assert AuditAction.BACKUP == "backup"
    assert AuditAction.UPDATE == "update"
    assert AuditAction.ADMIN_DENIED == "admin_denied"
    assert AuditAction.RATE_LIMIT_HIT == "rate_limit_hit"


def test_audit_logger_does_not_raise() -> None:
    logger = AuditLogger()
    logger.log(
        actor_id=123,
        action=AuditAction.CREATE_CLIENT,
        target_type="client",
        target_id="test-user",
        status="success",
        details="created",
    )
