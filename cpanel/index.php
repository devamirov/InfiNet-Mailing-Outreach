<?php
/**
 * InfiNet Outreach Control Panel – cpanel.infinetmail.services
 * Password-protected; run bot commands, STOP switch, edit email template.
 * Password is read from a file OUTSIDE the web root (../.panel_secret) or env PANEL_PASSWORD.
 */
session_start();

$panel_root = dirname(__DIR__);
$secret_file = $panel_root . '/.panel_secret';
if (function_exists('getenv') && getenv('PANEL_PASSWORD') !== false) {
    define('PANEL_PASSWORD', getenv('PANEL_PASSWORD'));
} elseif (is_file($secret_file) && is_readable($secret_file)) {
    define('PANEL_PASSWORD', trim(file_get_contents($secret_file)));
} else {
    define('PANEL_PASSWORD', '');
}
define('BOT_DIR', $panel_root . '/outreachbot');
define('STOP_FILE', BOT_DIR . '/STOP');
define('TEMPLATE_FILE', BOT_DIR . '/email_template.txt');

$DEFAULT_TEMPLATE = "Hi {name},

{headline}{city_line} – {tagline}

Check our current offer: {landing_page}

More about us: {main_site}

{opt_out_line}";

function is_authenticated(): bool {
    return !empty($_SESSION['panel_auth']);
}

function bot_stopped(): bool {
    return file_exists(STOP_FILE);
}

function ensure_bot_dir(): bool {
    return is_dir(BOT_DIR);
}

function run_bot_command(string $cmd): string {
    $python = BOT_DIR . '/.venv/bin/python';
    if (!is_executable($python)) {
        $python = 'python3';
    }
    $full = 'cd ' . escapeshellarg(BOT_DIR) . ' && ' . escapeshellarg($python) . ' -m src.main ' . $cmd . ' 2>&1';
    return shell_exec($full) ?? '';
}

// Login
if ($_SERVER['REQUEST_METHOD'] === 'POST' && isset($_POST['password'])) {
    if ($_POST['password'] === PANEL_PASSWORD) {
        $_SESSION['panel_auth'] = true;
        header('Location: ' . $_SERVER['REQUEST_URI']);
        exit;
    }
    $login_error = 'Wrong password.';
}

// Logout
if (isset($_GET['logout'])) {
    unset($_SESSION['panel_auth']);
    header('Location: ' . strtok($_SERVER['REQUEST_URI'], '?'));
    exit;
}

// Actions (require auth)
$output = '';
if (is_authenticated() && $_SERVER['REQUEST_METHOD'] === 'POST' && isset($_POST['action'])) {
    $action = $_POST['action'];
    if ($action === 'validate') {
        $output = run_bot_command('validate');
    } elseif ($action === 'dry_run') {
        $output = run_bot_command('run --mode dry_run');
    } elseif ($action === 'live') {
        $output = run_bot_command('run --mode live');
    } elseif ($action === 'report') {
        $output = run_bot_command('report');
    } elseif ($action === 'stop_on') {
        if (file_put_contents(STOP_FILE, '') !== false) {
            $output = "Bot stopped. STOP file created.";
        } else {
            $output = "Error: could not create STOP file.";
        }
    } elseif ($action === 'stop_off') {
        if (file_exists(STOP_FILE) && unlink(STOP_FILE)) {
            $output = "Bot can run. STOP file removed.";
        } else {
            $output = "STOP file was not present or could not be removed.";
        }
    } elseif ($action === 'save_template' && isset($_POST['template'])) {
        $content = $_POST['template'];
        if (file_put_contents(TEMPLATE_FILE, $content) !== false) {
            $output = "Template saved.";
        } else {
            $output = "Error: could not save template.";
        }
    }
}

// Read template for editor
$template_content = $DEFAULT_TEMPLATE;
if (is_authenticated() && file_exists(TEMPLATE_FILE)) {
    $template_content = file_get_contents(TEMPLATE_FILE);
    if ($template_content === false) {
        $template_content = $DEFAULT_TEMPLATE;
    }
}

// Show login form if not authenticated
if (!is_authenticated()) {
    header('Content-Type: text/html; charset=utf-8');
    ?>
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>InfiNet Outreach Panel – Login</title>
    <link rel="stylesheet" href="style.css">
</head>
<body class="login-page">
    <main class="login-box">
        <h1>InfiNet Outreach Panel</h1>
        <p>Enter password to continue.</p>
        <?php if (!empty($login_error)): ?><p class="error"><?= htmlspecialchars($login_error) ?></p><?php endif; ?>
        <form method="post">
            <input type="password" name="password" placeholder="Password" required autofocus>
            <button type="submit">Log in</button>
        </form>
    </main>
</body>
</html>
    <?php
    exit;
}

header('Content-Type: text/html; charset=utf-8');
?>
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>InfiNet Outreach Panel</title>
    <link rel="stylesheet" href="style.css">
</head>
<body>
    <header class="panel-header">
        <h1>InfiNet Outreach Panel</h1>
        <a href="?logout=1" class="logout">Log out</a>
    </header>

    <main class="panel-main">
        <section class="card">
            <h2>Bot status</h2>
            <p class="status <?= bot_stopped() ? 'stopped' : 'running' ?>">
                <?= bot_stopped() ? 'Bot is stopped (STOP file present)' : 'Bot can run' ?>
            </p>
            <form method="post" class="inline">
                <?php if (bot_stopped()): ?>
                    <input type="hidden" name="action" value="stop_off">
                    <button type="submit">Allow bot to run</button>
                <?php else: ?>
                    <input type="hidden" name="action" value="stop_on">
                    <button type="submit" class="danger">Stop bot</button>
                <?php endif; ?>
            </form>
        </section>

        <section class="card">
            <h2>Commands</h2>
            <p class="hint">Run bot commands (use Dry Run first to test without sending).</p>
            <div class="buttons">
                <form method="post" class="inline">
                    <input type="hidden" name="action" value="validate">
                    <button type="submit">Validate</button>
                </form>
                <form method="post" class="inline">
                    <input type="hidden" name="action" value="dry_run">
                    <button type="submit">Dry Run</button>
                </form>
                <form method="post" class="inline">
                    <input type="hidden" name="action" value="live">
                    <button type="submit">Live Run</button>
                </form>
                <form method="post" class="inline">
                    <input type="hidden" name="action" value="report">
                    <button type="submit">Report</button>
                </form>
            </div>
        </section>

        <?php if ($output !== ''): ?>
        <section class="card output-card">
            <h2>Last output</h2>
            <pre class="output"><?= htmlspecialchars($output) ?></pre>
        </section>
        <?php endif; ?>

        <section class="card">
            <h2>Email template</h2>
            <p class="hint">Placeholders: {name}, {city}, {city_line}, {headline}, {tagline}, {landing_page}, {main_site}, {opt_out_line}</p>
            <form method="post">
                <input type="hidden" name="action" value="save_template">
                <textarea name="template" rows="14" placeholder="Email body template"><?= htmlspecialchars($template_content) ?></textarea>
                <button type="submit">Save template</button>
            </form>
        </section>
    </main>
</body>
</html>
