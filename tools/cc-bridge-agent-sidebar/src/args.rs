use std::env;
use std::path::PathBuf;

use crate::theme::normalize_profile;

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Args {
    pub cc_bridge_daemon_socket: PathBuf,
    pub project_root: PathBuf,
    pub pane_window: String,
    pub theme: String,
}

impl Args {
    pub fn parse_from<I, S>(items: I) -> Result<Self, String>
    where
        I: IntoIterator<Item = S>,
        S: Into<String>,
    {
        Self::parse_from_inner(items, false)
    }

    fn parse_from_inner<I, S>(items: I, use_env_theme: bool) -> Result<Self, String>
    where
        I: IntoIterator<Item = S>,
        S: Into<String>,
    {
        let mut cc_bridge_daemon_socket: Option<PathBuf> = None;
        let mut project_root: Option<PathBuf> = None;
        let mut pane_window: Option<String> = None;
        let mut theme: Option<String> = None;
        let mut iter = items.into_iter().map(Into::into);

        while let Some(item) = iter.next() {
            match item.as_str() {
                "--cc_bridge_daemon-socket" => {
                    cc_bridge_daemon_socket = Some(PathBuf::from(next_value(&mut iter, "--cc_bridge_daemon-socket")?));
                }
                "--project-root" => {
                    project_root = Some(PathBuf::from(next_value(&mut iter, "--project-root")?));
                }
                "--pane-window" => {
                    pane_window = Some(non_empty(
                        next_value(&mut iter, "--pane-window")?,
                        "--pane-window",
                    )?);
                }
                "--theme" => {
                    theme = Some(theme_profile(next_value(&mut iter, "--theme")?)?);
                }
                "-h" | "--help" => return Err(usage()),
                other => return Err(format!("unknown argument: {other}\n{}", usage())),
            }
        }

        Ok(Self {
            cc_bridge_daemon_socket: cc_bridge_daemon_socket.ok_or_else(|| missing("--cc_bridge_daemon-socket"))?,
            project_root: project_root.ok_or_else(|| missing("--project-root"))?,
            pane_window: pane_window.ok_or_else(|| missing("--pane-window"))?,
            theme: theme
                .or_else(|| {
                    if use_env_theme {
                        theme_from_env()
                    } else {
                        None
                    }
                })
                .unwrap_or_else(|| "default".to_string()),
        })
    }

    pub fn parse_env() -> Result<Self, String> {
        Self::parse_from_inner(env::args().skip(1), true)
    }
}

fn next_value(iter: &mut impl Iterator<Item = String>, flag: &str) -> Result<String, String> {
    iter.next()
        .ok_or_else(|| format!("missing value for {flag}"))
}

fn non_empty(value: String, flag: &str) -> Result<String, String> {
    let text = value.trim().to_string();
    if text.is_empty() {
        Err(format!("empty value for {flag}"))
    } else {
        Ok(text)
    }
}

fn theme_profile(value: String) -> Result<String, String> {
    normalize_profile(&value).ok_or_else(|| format!("unsupported --theme value: {value}"))
}

fn theme_from_env() -> Option<String> {
    env::var("CC_BRIDGE_SIDEBAR_THEME_PROFILE")
        .ok()
        .and_then(|value| normalize_profile(&value))
        .or_else(|| {
            env::var("CC_BRIDGE_TMUX_THEME_PROFILE")
                .ok()
                .and_then(|value| normalize_profile(&value))
        })
}

fn missing(flag: &str) -> String {
    format!("missing required argument {flag}\n{}", usage())
}

pub fn usage() -> String {
    "usage: cc_bridge-agent-sidebar --cc_bridge_daemon-socket <path> --project-root <path> --pane-window <name> [--theme <profile>]"
        .to_string()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn parses_required_arguments() {
        let args = Args::parse_from([
            "--cc_bridge_daemon-socket",
            "/tmp/cc_bridge_daemon.sock",
            "--project-root",
            "/repo",
            "--pane-window",
            "main",
        ])
        .unwrap();

        assert_eq!(args.cc_bridge_daemon_socket, PathBuf::from("/tmp/cc_bridge_daemon.sock"));
        assert_eq!(args.project_root, PathBuf::from("/repo"));
        assert_eq!(args.pane_window, "main");
        assert_eq!(args.theme, "default");
    }

    #[test]
    fn rejects_missing_socket() {
        let err =
            Args::parse_from(["--project-root", "/repo", "--pane-window", "main"]).unwrap_err();
        assert!(err.contains("--cc_bridge_daemon-socket"));
    }

    #[test]
    fn parses_sidebar_theme() {
        let args = Args::parse_from([
            "--cc_bridge_daemon-socket",
            "/tmp/cc_bridge_daemon.sock",
            "--project-root",
            "/repo",
            "--pane-window",
            "main",
            "--theme",
            "light",
        ])
        .unwrap();

        assert_eq!(args.theme, "light");
    }
}
