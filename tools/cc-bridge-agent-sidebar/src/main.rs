use cc_bridge_agent_sidebar::args::{Args, usage};

fn main() {
    unsafe {
        std::env::remove_var("NO_COLOR");
    }

    let args = match Args::parse_env() {
        Ok(args) => args,
        Err(err) => {
            eprintln!("{err}");
            eprintln!("{}", usage());
            std::process::exit(2);
        }
    };

    if let Err(err) = cc_bridge_agent_sidebar::tui::run(args) {
        eprintln!("cc_bridge-agent-sidebar: {err}");
        std::process::exit(1);
    }
}
