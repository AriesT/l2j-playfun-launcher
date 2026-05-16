<?php
header('Content-Type: application/json; charset=utf-8');
header('Access-Control-Allow-Origin: *');

$BASE_DIR = '/opt/l2j_mobius/web/Lineage2PlayFun';
$BASE_URL = 'http://188.40.83.149/Lineage2PlayFun';

$action = $_GET['action'] ?? 'manifest';

if ($action === 'manifest') {
    $files = [];
    if (!is_dir($BASE_DIR)) {
        echo json_encode(['error' => 'Game directory not found']);
        exit;
    }
    $iterator = new RecursiveIteratorIterator(new RecursiveDirectoryIterator($BASE_DIR));
    foreach ($iterator as $file) {
        if ($file->isDir()) continue;
        $relativePath = str_replace($BASE_DIR . DIRECTORY_SEPARATOR, '', $file->getPathname());
        $relativePath = str_replace(DIRECTORY_SEPARATOR, '/', $relativePath);
        $files[] = [
            'path' => $relativePath,
            'size' => $file->getSize(),
            'md5' => md5_file($file->getPathname()),
            'url' => $BASE_URL . '/' . $relativePath
        ];
    }
    $version = trim(@file_get_contents('/opt/l2j_mobius/web/version.txt') ?: '1.0.0');
    echo json_encode(['version' => $version, 'files' => $files, 'total_files' => count($files)]);
    exit;
}

if ($action === 'version') {
    $version = trim(@file_get_contents('/opt/l2j_mobius/web/version.txt') ?: '1.0.0');
    echo json_encode(['version' => $version]);
    exit;
}

if ($action === 'status') {
    $login = shell_exec("pgrep -f 'LoginServer.jar' >/dev/null 2>&1 && echo online || echo offline");
    $game = shell_exec("pgrep -f 'GameServer.jar' >/dev/null 2>&1 && echo online || echo offline");
    $players = 0;
    try {
        $pdo = new PDO('mysql:host=localhost;dbname=l2j_M_gs;charset=utf8', 'l2j_M_user', 'L2j_M_PASSWORD');
        $pdo->setAttribute(PDO::ATTR_ERRMODE, PDO::ERRMODE_SILENT);
        $players = (int)$pdo->query("SELECT COUNT(*) FROM characters WHERE online = 1")->fetchColumn();
    } catch (Exception $e) {}
    echo json_encode([
        'login' => trim($login),
        'game' => trim($game),
        'players' => $players
    ]);
    exit;
}

echo json_encode(['error' => 'Unknown action']);
