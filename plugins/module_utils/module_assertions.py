from ansible.module_utils.basic import AnsibleModule

def assert_not_handling_check_mode_since_action_reponsibility(m: AnsibleModule) -> None:
  if m.check_mode:
    msg = f"module({m._name} should not be handling check mode "\
          "since this is the sole reponsibility of the corresponding action"
    raise RuntimeError(msg)