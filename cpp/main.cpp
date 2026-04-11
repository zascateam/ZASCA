#include <windows.h>
#include <aclapi.h>
#include <string>
#include <vector>
#include <iostream>
#include <cwctype>
#include <algorithm>
#include <winhttp.h>
#include <shlobj.h>
#include <shellapi.h>
#include <fstream>

#pragma comment(lib, "winhttp.lib")
#pragma comment(lib, "shell32.lib")

#define SERVICE_NAME "DjangoGuardSvc"
#define DISPLAY_NAME "Django Environment Guard Service"
#define GITHUB_API_URL "api.github.com"
#define GITHUB_RELEASES_PATH "/repos/trustedinster/ZASCA/releases"
#define MIRROR_BASE_URL "https://ghproxy.sectl.top/"

SERVICE_STATUS        g_ServiceStatus = {0};
SERVICE_STATUS_HANDLE g_StatusHandle = NULL;
HANDLE                g_ServiceStopEvent = INVALID_HANDLE_VALUE;
std::string           g_Port = "8000";

int ShowMessage(const std::string& title, const std::string& msg, UINT type);
bool IsNumber(const std::string& s);
DWORD GetServiceState();
void InstallAndStartService(const std::string& port);
void StopAndUninstallService();
void HandleControlCommand(const std::string& action, const std::string& port);
void HandlePassthrough(const std::vector<std::string>& args);
void HandleInit();
void HandleUpdate();

void ServiceMain(DWORD argc, LPTSTR* argv);
void ServiceCtrlHandler(DWORD CtrlCode);
void WorkerThread();
DWORD RunCommand(const std::string& cmd, bool isProtected = false);
void RefreshEnvironment();
PSECURITY_DESCRIPTOR CreateProtectedSD();

LPVOID CreateChinaMirrorEnvBlock();
void FreeEnvBlock(LPVOID env);
BOOL ExecuteCommand(const std::string& cmd, DWORD flags, bool isProtected, LPHANDLE hProcessOut = NULL);

std::string HttpGet(const std::string& host, const std::string& path);
bool DownloadFile(const std::string& url, const std::string& localPath);
bool ExtractZip(const std::string& zipPath, const std::string& destPath);
std::string ParseJsonString(const std::string& json, const std::string& key);
std::string GetTempFilePath();
std::string GetExeDirectory();
bool UpdateFromRelease(const std::string& zipUrl);
bool CopyDirectoryRecursive(const std::string& srcPath, const std::string& destPath);
bool RemoveDirectoryRecursive(const std::string& dirPath);

std::wstring Utf8ToWide(const std::string& str) {
    if (str.empty()) return std::wstring();
    int size = MultiByteToWideChar(CP_UTF8, 0, str.c_str(), -1, NULL, 0);
    if (size == 0) return std::wstring();
    std::wstring result(size - 1, 0);
    MultiByteToWideChar(CP_UTF8, 0, str.c_str(), -1, &result[0], size);
    return result;
}

int ShowMessage(const std::string& title, const std::string& msg, UINT type = MB_OK) {
    return MessageBoxW(NULL, Utf8ToWide(msg).c_str(), Utf8ToWide(title).c_str(), type | MB_TOPMOST);
}

bool IsNumber(const std::string& s) {
    if (s.empty()) return false;
    for (char c : s) if (!std::isdigit(c)) return false;
    return true;
}

DWORD GetServiceState() {
    SC_HANDLE scm = OpenSCManagerA(NULL, NULL, SC_MANAGER_CONNECT);
    if (!scm) return SERVICE_STOPPED;
    SC_HANDLE svc = OpenServiceA(scm, SERVICE_NAME, SERVICE_QUERY_STATUS);
    if (!svc) { CloseServiceHandle(scm); return SERVICE_STOPPED; }
    SERVICE_STATUS status;
    if (QueryServiceStatus(svc, &status)) { CloseServiceHandle(svc); CloseServiceHandle(scm); return status.dwCurrentState; }
    CloseServiceHandle(svc); CloseServiceHandle(scm);
    return SERVICE_STOPPED;
}

PSECURITY_DESCRIPTOR CreateProtectedSD() {
    PACL pACL = NULL;
    PSECURITY_DESCRIPTOR pSD = (PSECURITY_DESCRIPTOR)LocalAlloc(LPTR, SECURITY_DESCRIPTOR_MIN_LENGTH);
    if (!pSD || !InitializeSecurityDescriptor(pSD, SECURITY_DESCRIPTOR_REVISION)) return NULL;
    EXPLICIT_ACCESS ea[3]; ZeroMemory(ea, sizeof(ea));
    
    ea[0].grfAccessPermissions = PROCESS_TERMINATE; ea[0].grfAccessMode = DENY_ACCESS;
    ea[0].grfInheritance = NO_INHERITANCE; ea[0].Trustee.TrusteeForm = TRUSTEE_IS_NAME;
    ea[0].Trustee.TrusteeType = TRUSTEE_IS_GROUP; ea[0].Trustee.ptstrName = (LPTSTR)"INTERACTIVE";

    ea[1].grfAccessPermissions = PROCESS_ALL_ACCESS; ea[1].grfAccessMode = SET_ACCESS;
    ea[1].grfInheritance = NO_INHERITANCE; ea[1].Trustee.TrusteeForm = TRUSTEE_IS_NAME;
    ea[1].Trustee.TrusteeType = TRUSTEE_IS_WELL_KNOWN_GROUP; ea[1].Trustee.ptstrName = (LPTSTR)"SYSTEM";

    ea[2].grfAccessPermissions = PROCESS_ALL_ACCESS; ea[2].grfAccessMode = SET_ACCESS;
    ea[2].grfInheritance = NO_INHERITANCE; ea[2].Trustee.TrusteeForm = TRUSTEE_IS_NAME;
    ea[2].Trustee.TrusteeType = TRUSTEE_IS_WELL_KNOWN_GROUP; ea[2].Trustee.ptstrName = (LPTSTR)"Administrators";

    if (SetEntriesInAcl(3, ea, NULL, &pACL) != ERROR_SUCCESS) return NULL;
    SetSecurityDescriptorDacl(pSD, TRUE, pACL, FALSE);
    return pSD;
}

LPVOID CreateChinaMirrorEnvBlock() {
    LPCH parentEnv = GetEnvironmentStrings();
    std::string envBlock;
    
    for (LPCH p = parentEnv; *p; p += strlen(p) + 1) {
        std::string entry = p;
        if (entry.find("UV_INDEX_URL=") == 0 || entry.find("UV_EXTRA_INDEX_URL=") == 0) continue;
        if (entry.find("UV_PYTHON_INSTALL_MIRROR=") == 0) continue;
        if (entry.find("UV_INSTALLER_GITHUB_BASE_URL=") == 0) continue;
        
        envBlock += entry + '\0';
    }
    FreeEnvironmentStrings(parentEnv);

    envBlock += "UV_INSTALLER_GITHUB_BASE_URL=https://ghfast.top/https://github.com/\0";
    envBlock += "UV_PYTHON_INSTALL_MIRROR=https://mirrors.tuna.tsinghua.edu.cn/python/\0";
    envBlock += "UV_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple\0";
    
    envBlock += '\0';

    LPVOID envMem = LocalAlloc(LPTR, envBlock.length());
    if (envMem) memcpy(envMem, envBlock.c_str(), envBlock.length());
    return envMem;
}

void FreeEnvBlock(LPVOID env) { if (env) LocalFree(env); }

BOOL ExecuteCommand(const std::string& cmd, DWORD flags, bool isProtected, LPHANDLE hProcessOut) {
    STARTUPINFOA si; PROCESS_INFORMATION pi;
    ZeroMemory(&si, sizeof(si)); si.cb = sizeof(si);
    if (flags & CREATE_NO_WINDOW) { si.dwFlags = STARTF_USESHOWWINDOW; si.wShowWindow = SW_HIDE; }
    ZeroMemory(&pi, sizeof(pi));

    SECURITY_ATTRIBUTES sa = {0}; PSECURITY_DESCRIPTOR pSD = NULL;
    if (isProtected) {
        pSD = CreateProtectedSD();
        if (pSD) { sa.nLength = sizeof(SECURITY_ATTRIBUTES); sa.lpSecurityDescriptor = pSD; sa.bInheritHandle = FALSE; }
    }

    LPVOID envBlock = CreateChinaMirrorEnvBlock();
    char* cmdBuf = new char[cmd.length() + 1]; strcpy_s(cmdBuf, cmd.length() + 1, cmd.c_str());

    BOOL success = CreateProcessA(NULL, cmdBuf, isProtected ? &sa : NULL, NULL, FALSE, flags, envBlock, NULL, &si, &pi);
    
    delete[] cmdBuf;
    FreeEnvBlock(envBlock);
    if (pSD) LocalFree(pSD);

    if (success) {
        CloseHandle(pi.hThread);
        if (hProcessOut) *hProcessOut = pi.hProcess; else CloseHandle(pi.hProcess);
    }
    return success;
}

std::string HttpGet(const std::string& host, const std::string& path) {
    std::string response;
    HINTERNET hSession = WinHttpOpen(L"ZASCA-Updater/1.0", WINHTTP_ACCESS_TYPE_DEFAULT_PROXY, NULL, NULL, 0);
    if (!hSession) return response;

    std::wstring wHost(host.begin(), host.end());
    HINTERNET hConnect = WinHttpConnect(hSession, wHost.c_str(), INTERNET_DEFAULT_HTTPS_PORT, 0);
    if (!hConnect) { WinHttpCloseHandle(hSession); return response; }

    std::wstring wPath(path.begin(), path.end());
    HINTERNET hRequest = WinHttpOpenRequest(hConnect, L"GET", wPath.c_str(), NULL, NULL, NULL, WINHTTP_FLAG_SECURE);
    if (!hRequest) { WinHttpCloseHandle(hConnect); WinHttpCloseHandle(hSession); return response; }

    BOOL bResults = WinHttpSendRequest(hRequest, NULL, 0, NULL, 0, 0, 0);
    if (bResults) {
        bResults = WinHttpReceiveResponse(hRequest, NULL);
        if (bResults) {
            DWORD dwSize = 0;
            do {
                DWORD dwDownloaded = 0;
                if (!WinHttpQueryDataAvailable(hRequest, &dwSize)) break;
                if (dwSize == 0) break;
                
                std::vector<char> buffer(dwSize + 1);
                if (!WinHttpReadData(hRequest, &buffer[0], dwSize, &dwDownloaded)) break;
                
                response.append(&buffer[0], dwDownloaded);
            } while (dwSize > 0);
        }
    }

    WinHttpCloseHandle(hRequest);
    WinHttpCloseHandle(hConnect);
    WinHttpCloseHandle(hSession);
    return response;
}

bool DownloadFile(const std::string& url, const std::string& localPath) {
    std::string host, path;
    size_t protoEnd = url.find("://");
    if (protoEnd == std::string::npos) return false;
    
    std::string afterProto = url.substr(protoEnd + 3);
    size_t pathStart = afterProto.find('/');
    if (pathStart == std::string::npos) return false;
    
    host = afterProto.substr(0, pathStart);
    path = afterProto.substr(pathStart);

    HINTERNET hSession = WinHttpOpen(L"ZASCA-Updater/1.0", WINHTTP_ACCESS_TYPE_DEFAULT_PROXY, NULL, NULL, 0);
    if (!hSession) return false;

    std::wstring wHost(host.begin(), host.end());
    bool isHttps = (url.find("https://") == 0);
    INTERNET_PORT port = isHttps ? INTERNET_DEFAULT_HTTPS_PORT : INTERNET_DEFAULT_HTTP_PORT;
    
    HINTERNET hConnect = WinHttpConnect(hSession, wHost.c_str(), port, 0);
    if (!hConnect) { WinHttpCloseHandle(hSession); return false; }

    std::wstring wPath(path.begin(), path.end());
    DWORD flags = isHttps ? WINHTTP_FLAG_SECURE : 0;
    HINTERNET hRequest = WinHttpOpenRequest(hConnect, L"GET", wPath.c_str(), NULL, NULL, NULL, flags);
    if (!hRequest) { WinHttpCloseHandle(hConnect); WinHttpCloseHandle(hSession); return false; }

    BOOL bResults = WinHttpSendRequest(hRequest, NULL, 0, NULL, 0, 0, 0);
    if (bResults) {
        bResults = WinHttpReceiveResponse(hRequest, NULL);
        if (bResults) {
            std::ofstream outFile(localPath, std::ios::binary);
            if (!outFile.is_open()) {
                WinHttpCloseHandle(hRequest);
                WinHttpCloseHandle(hConnect);
                WinHttpCloseHandle(hSession);
                return false;
            }

            DWORD dwSize = 0;
            do {
                DWORD dwDownloaded = 0;
                if (!WinHttpQueryDataAvailable(hRequest, &dwSize)) break;
                if (dwSize == 0) break;
                
                std::vector<char> buffer(dwSize);
                if (!WinHttpReadData(hRequest, &buffer[0], dwSize, &dwDownloaded)) break;
                
                outFile.write(&buffer[0], dwDownloaded);
            } while (dwSize > 0);
            
            outFile.close();
        }
    }

    WinHttpCloseHandle(hRequest);
    WinHttpCloseHandle(hConnect);
    WinHttpCloseHandle(hSession);
    return bResults == TRUE;
}

std::string ParseJsonString(const std::string& json, const std::string& key) {
    std::string searchKey = "\"" + key + "\"";
    size_t keyPos = json.find(searchKey);
    if (keyPos == std::string::npos) return "";
    
    size_t colonPos = json.find(':', keyPos);
    if (colonPos == std::string::npos) return "";
    
    size_t quoteStart = json.find('"', colonPos);
    if (quoteStart == std::string::npos) return "";
    
    std::string result;
    bool escape = false;
    for (size_t i = quoteStart + 1; i < json.length(); i++) {
        char c = json[i];
        if (escape) {
            switch (c) {
                case '"': result += '"'; break;
                case '\\': result += '\\'; break;
                case '/': result += '/'; break;
                case 'b': result += '\b'; break;
                case 'f': result += '\f'; break;
                case 'n': result += '\n'; break;
                case 'r': result += '\r'; break;
                case 't': result += '\t'; break;
                case 'u': {
                    if (i + 4 < json.length()) {
                        unsigned int codepoint = 0;
                        bool validHex = true;
                        for (int j = 0; j < 4; j++) {
                            codepoint <<= 4;
                            char hex = json[i + 1 + j];
                            if (hex >= '0' && hex <= '9') codepoint |= (hex - '0');
                            else if (hex >= 'a' && hex <= 'f') codepoint |= (hex - 'a' + 10);
                            else if (hex >= 'A' && hex <= 'F') codepoint |= (hex - 'A' + 10);
                            else { validHex = false; break; }
                        }
                        if (validHex) {
                            if (codepoint < 0x80) {
                                result += static_cast<char>(codepoint);
                            } else if (codepoint < 0x800) {
                                result += static_cast<char>(0xC0 | (codepoint >> 6));
                                result += static_cast<char>(0x80 | (codepoint & 0x3F));
                            } else {
                                result += static_cast<char>(0xE0 | (codepoint >> 12));
                                result += static_cast<char>(0x80 | ((codepoint >> 6) & 0x3F));
                                result += static_cast<char>(0x80 | (codepoint & 0x3F));
                            }
                            i += 4;
                        } else {
                            result += '?';
                        }
                    } else {
                        result += '?';
                    }
                    break;
                }
                default: result += c; break;
            }
            escape = false;
        } else if (c == '\\') {
            escape = true;
        } else if (c == '"') {
            return result;
        } else {
            result += c;
        }
    }
    return result;
}

bool CopyDirectoryRecursive(const std::string& srcPath, const std::string& destPath) {
    if (!CreateDirectoryA(destPath.c_str(), NULL)) {
        if (GetLastError() != ERROR_ALREADY_EXISTS) return false;
    }
    
    WIN32_FIND_DATAA findData;
    std::string searchPath = srcPath + "\\*";
    HANDLE hFind = FindFirstFileA(searchPath.c_str(), &findData);
    
    if (hFind == INVALID_HANDLE_VALUE) return false;
    
    bool success = true;
    do {
        if (strcmp(findData.cFileName, ".") == 0 || strcmp(findData.cFileName, "..") == 0) continue;
        
        std::string srcItem = srcPath + "\\" + findData.cFileName;
        std::string destItem = destPath + "\\" + findData.cFileName;
        
        if (findData.dwFileAttributes & FILE_ATTRIBUTE_DIRECTORY) {
            if (!CopyDirectoryRecursive(srcItem, destItem)) success = false;
        } else {
            if (!CopyFileA(srcItem.c_str(), destItem.c_str(), FALSE)) success = false;
        }
    } while (FindNextFileA(hFind, &findData));
    
    FindClose(hFind);
    return success;
}

bool RemoveDirectoryRecursive(const std::string& dirPath) {
    WIN32_FIND_DATAA findData;
    std::string searchPath = dirPath + "\\*";
    HANDLE hFind = FindFirstFileA(searchPath.c_str(), &findData);
    
    if (hFind == INVALID_HANDLE_VALUE) return false;
    
    bool success = true;
    do {
        if (strcmp(findData.cFileName, ".") == 0 || strcmp(findData.cFileName, "..") == 0) continue;
        
        std::string itemPath = dirPath + "\\" + findData.cFileName;
        
        if (findData.dwFileAttributes & FILE_ATTRIBUTE_DIRECTORY) {
            if (!RemoveDirectoryRecursive(itemPath)) success = false;
        } else {
            if (!DeleteFileA(itemPath.c_str())) success = false;
        }
    } while (FindNextFileA(hFind, &findData));
    
    FindClose(hFind);
    
    if (!RemoveDirectoryA(dirPath.c_str())) success = false;
    return success;
}

std::string GetTempFilePath() {
    char tempPath[MAX_PATH];
    GetTempPathA(MAX_PATH, tempPath);
    char tempFile[MAX_PATH];
    GetTempFileNameA(tempPath, "ZASCA", 0, tempFile);
    return std::string(tempFile);
}

std::string GetExeDirectory() {
    char exePath[MAX_PATH];
    GetModuleFileNameA(NULL, exePath, MAX_PATH);
    std::string dir = exePath;
    size_t pos = dir.find_last_of("\\");
    return (pos != std::string::npos) ? dir.substr(0, pos) : dir;
}

bool ExtractZip(const std::string& zipPath, const std::string& destPath) {
    std::wstring wZipPath(zipPath.begin(), zipPath.end());
    std::wstring wDestPath(destPath.begin(), destPath.end());
    
    HRESULT hr = CoInitialize(NULL);
    if (FAILED(hr)) return false;
    
    IShellDispatch* pShell = NULL;
    hr = CoCreateInstance(CLSID_Shell, NULL, CLSCTX_INPROC_SERVER, IID_IShellDispatch, (void**)&pShell);
    if (FAILED(hr)) { CoUninitialize(); return false; }
    
    Folder* pZipFile = NULL;
    VARIANT varZipPath; varZipPath.vt = VT_BSTR; varZipPath.bstrVal = SysAllocString(wZipPath.c_str());
    hr = pShell->NameSpace(varZipPath, &pZipFile);
    SysFreeString(varZipPath.bstrVal);
    
    if (FAILED(hr) || !pZipFile) { pShell->Release(); CoUninitialize(); return false; }
    
    Folder* pDestFolder = NULL;
    VARIANT varDestPath; varDestPath.vt = VT_BSTR; varDestPath.bstrVal = SysAllocString(wDestPath.c_str());
    hr = pShell->NameSpace(varDestPath, &pDestFolder);
    SysFreeString(varDestPath.bstrVal);
    
    if (FAILED(hr) || !pDestFolder) { pZipFile->Release(); pShell->Release(); CoUninitialize(); return false; }
    
    FolderItems* pItems = NULL;
    hr = pZipFile->Items(&pItems);
    if (FAILED(hr) || !pItems) { pDestFolder->Release(); pZipFile->Release(); pShell->Release(); CoUninitialize(); return false; }
    
    long itemCount = 0;
    pItems->get_Count(&itemCount);
    
    VARIANT varItems; varItems.vt = VT_DISPATCH; varItems.pdispVal = (IDispatch*)pItems;
    VARIANT varOptions; varOptions.vt = VT_I4; varOptions.lVal = 0;
    
    hr = pDestFolder->CopyHere(varItems, varOptions);
    
    Sleep(1000);
    
    pItems->Release();
    pDestFolder->Release();
    pZipFile->Release();
    pShell->Release();
    CoUninitialize();
    
    return SUCCEEDED(hr);
}

bool UpdateFromRelease(const std::string& zipUrl) {
    std::string tempZip = GetTempFilePath() + ".zip";
    std::string tempDir = GetTempFilePath();
    CreateDirectoryA(tempDir.c_str(), NULL);
    
    ShowMessage("更新中", "正在下载最新版本...", MB_ICONINFORMATION);
    
    if (!DownloadFile(zipUrl, tempZip)) {
        ShowMessage("错误", "下载失败，请检查网络连接。", MB_ICONERROR);
        DeleteFileA(tempZip.c_str());
        RemoveDirectoryA(tempDir.c_str());
        return false;
    }
    
    ShowMessage("更新中", "正在解压文件...", MB_ICONINFORMATION);
    
    if (!ExtractZip(tempZip, tempDir)) {
        ShowMessage("错误", "解压失败。", MB_ICONERROR);
        DeleteFileA(tempZip.c_str());
        RemoveDirectoryA(tempDir.c_str());
        return false;
    }
    
    std::string exeDir = GetExeDirectory();
    
    WIN32_FIND_DATAA findData;
    std::string searchPath = tempDir + "\\*";
    HANDLE hFind = FindFirstFileA(searchPath.c_str(), &findData);
    
    std::string extractedDir = tempDir;
    if (hFind != INVALID_HANDLE_VALUE) {
        do {
            if (findData.dwFileAttributes & FILE_ATTRIBUTE_DIRECTORY) {
                if (strcmp(findData.cFileName, ".") != 0 && strcmp(findData.cFileName, "..") != 0) {
                    extractedDir = tempDir + "\\" + findData.cFileName;
                    break;
                }
            }
        } while (FindNextFileA(hFind, &findData));
        FindClose(hFind);
    }
    
    ShowMessage("更新中", "正在复制文件...", MB_ICONINFORMATION);
    
    searchPath = extractedDir + "\\*";
    hFind = FindFirstFileA(searchPath.c_str(), &findData);
    
    if (hFind != INVALID_HANDLE_VALUE) {
        do {
            if (strcmp(findData.cFileName, ".") != 0 && strcmp(findData.cFileName, "..") != 0) {
                std::string srcPath = extractedDir + "\\" + findData.cFileName;
                std::string destPath = exeDir + "\\" + findData.cFileName;
                
                if (findData.dwFileAttributes & FILE_ATTRIBUTE_DIRECTORY) {
                    CopyDirectoryRecursive(srcPath, destPath);
                } else {
                    CopyFileA(srcPath.c_str(), destPath.c_str(), FALSE);
                }
            }
        } while (FindNextFileA(hFind, &findData));
        FindClose(hFind);
    }
    
    DeleteFileA(tempZip.c_str());
    
    searchPath = tempDir + "\\*";
    hFind = FindFirstFileA(searchPath.c_str(), &findData);
    if (hFind != INVALID_HANDLE_VALUE) {
        do {
            if (findData.dwFileAttributes & FILE_ATTRIBUTE_DIRECTORY) {
                if (strcmp(findData.cFileName, ".") != 0 && strcmp(findData.cFileName, "..") != 0) {
                    std::string subDir = tempDir + "\\" + findData.cFileName;
                    RemoveDirectoryRecursive(subDir);
                }
            } else {
                std::string filePath = tempDir + "\\" + findData.cFileName;
                DeleteFileA(filePath.c_str());
            }
        } while (FindNextFileA(hFind, &findData));
        FindClose(hFind);
    }
    RemoveDirectoryA(tempDir.c_str());
    
    return true;
}

void HandleUpdate() {
    ShowMessage("检查更新", "正在检查最新版本...", MB_ICONINFORMATION);
    
    std::string response = HttpGet(GITHUB_API_URL, GITHUB_RELEASES_PATH);
    if (response.empty()) {
        ShowMessage("错误", "无法连接到 GitHub API，请检查网络连接。", MB_ICONERROR);
        return;
    }
    
    size_t releaseStart = response.find('{');
    if (releaseStart == std::string::npos) {
        ShowMessage("错误", "无法解析 GitHub API 响应。", MB_ICONERROR);
        return;
    }
    
    std::string firstRelease = response.substr(releaseStart);
    size_t releaseEnd = firstRelease.find("},");
    if (releaseEnd != std::string::npos) {
        firstRelease = firstRelease.substr(0, releaseEnd + 1);
    }
    
    std::string zipUrl = ParseJsonString(firstRelease, "zipball_url");
    std::string tagName = ParseJsonString(firstRelease, "tag_name");
    
    if (zipUrl.empty()) {
        ShowMessage("错误", "无法获取下载链接。", MB_ICONERROR);
        return;
    }
    
    std::string mirrorUrl = MIRROR_BASE_URL + zipUrl;
    
    std::string msg = "发现最新版本: " + tagName + "\n\n是否立即更新？\n\n下载源: " + mirrorUrl;
    int result = MessageBoxW(NULL, Utf8ToWide(msg).c_str(), Utf8ToWide("发现更新").c_str(), MB_YESNO | MB_ICONQUESTION | MB_TOPMOST);
    
    if (result == IDYES) {
        if (UpdateFromRelease(mirrorUrl)) {
            ShowMessage("成功", "更新完成！程序即将重启。", MB_ICONINFORMATION);
            
            char exePath[MAX_PATH];
            GetModuleFileNameA(NULL, exePath, MAX_PATH);
            
            STARTUPINFOA si; PROCESS_INFORMATION pi;
            ZeroMemory(&si, sizeof(si)); si.cb = sizeof(si);
            ZeroMemory(&pi, sizeof(pi));
            
            CreateProcessA(NULL, exePath, NULL, NULL, FALSE, 0, NULL, NULL, &si, &pi);
            CloseHandle(pi.hThread);
            CloseHandle(pi.hProcess);
            
            exit(0);
        }
    } else {
        ShowMessage("取消", "更新已取消。", MB_ICONINFORMATION);
    }
}

void InstallAndStartService(const std::string& port) {
    char exePath[MAX_PATH]; GetModuleFileNameA(NULL, exePath, MAX_PATH);
    std::string cmdLine = std::string("\"") + exePath + "\" --run " + port;
    SC_HANDLE schSCManager = OpenSCManagerA(NULL, NULL, SC_MANAGER_ALL_ACCESS);
    if (!schSCManager) { ShowMessage("错误", "无法打开服务控制管理器，请确保以管理员身份运行。", MB_ICONERROR); return; }

    SC_HANDLE schService = CreateServiceA(schSCManager, SERVICE_NAME, DISPLAY_NAME, SERVICE_ALL_ACCESS, SERVICE_WIN32_OWN_PROCESS, SERVICE_AUTO_START, SERVICE_ERROR_IGNORE, cmdLine.c_str(), NULL, NULL, NULL, NULL, NULL);
    if (!schService && GetLastError() == ERROR_SERVICE_EXISTS) {
        schService = OpenServiceA(schSCManager, SERVICE_NAME, SERVICE_ALL_ACCESS);
        ChangeServiceConfigA(schService, SERVICE_WIN32_OWN_PROCESS, SERVICE_AUTO_START, SERVICE_ERROR_IGNORE, cmdLine.c_str(), NULL, NULL, NULL, NULL, NULL, NULL);
    }
    if (schService) {
        std::string dir = exePath; dir = dir.substr(0, dir.find_last_of("\\"));
        std::string icaclsCmd = "icacls \"" + dir + "\" /deny \"Users:(OI)(CI)(DE,DC)\" /deny \"INTERACTIVE:(OI)(CI)(DE,DC)\" /T /C /Q";
        WinExec(icaclsCmd.c_str(), SW_HIDE);
        StartServiceA(schService, 0, NULL);
        ShowMessage("成功", "服务已启动并在后台守护运行。", MB_ICONINFORMATION);
        CloseServiceHandle(schService);
    } else { ShowMessage("错误", "无法创建或打开服务。", MB_ICONERROR); }
    CloseServiceHandle(schSCManager);
}

void StopAndUninstallService() {
    SC_HANDLE scm = OpenSCManagerA(NULL, NULL, SC_MANAGER_ALL_ACCESS); if (!scm) return;
    SC_HANDLE svc = OpenServiceA(scm, SERVICE_NAME, SERVICE_STOP | DELETE);
    if (svc) {
        SERVICE_STATUS status; ControlService(svc, SERVICE_CONTROL_STOP, &status);
        while (GetServiceState() != SERVICE_STOPPED) Sleep(500);
        DeleteService(svc); CloseHandle(svc);
        ShowMessage("成功", "服务已停止并卸载。", MB_ICONINFORMATION);
    } else { ShowMessage("提示", "服务未运行或未安装。", MB_ICONINFORMATION); }
    CloseServiceHandle(scm);
}

void HandleControlCommand(const std::string& action, const std::string& port) {
    if (action == "stop") { StopAndUninstallService(); return; }
    if (action == "restart") { StopAndUninstallService(); while (GetServiceState() != SERVICE_STOPPED) Sleep(200); InstallAndStartService(port); return; }
    
    if (action == "start") {
        DWORD state = GetServiceState();
        if (state == SERVICE_RUNNING) {
            std::string msg = "检测到服务已在运行。\n\n【是】：关闭现有服务并重新启动。\n【否】：忽略警告，单开一个黑框前台运行(用于多端口调试，不守护)。\n【取消】：放弃操作。";
            int res = ShowMessage("冲突警告", msg, MB_YESNOCANCEL | MB_ICONWARNING);
            if (res == IDYES) { StopAndUninstallService(); while (GetServiceState() != SERVICE_STOPPED) Sleep(200); InstallAndStartService(port); return; }
            else if (res == IDNO) { ExecuteCommand("uv run python manage.py runserver " + port, CREATE_NEW_CONSOLE, false); return; }
            else return;
        } else { InstallAndStartService(port); }
    }
}

void HandlePassthrough(const std::vector<std::string>& args) {
    std::string fullCmd = "uv run python manage.py";
    for (const auto& arg : args) fullCmd += " " + arg;
    if (!ExecuteCommand(fullCmd, CREATE_NEW_CONSOLE, false)) {
        ShowMessage("执行出错", "无法启动进程，请检查 uv 和 python 环境。", MB_ICONERROR);
    }
}

void HandleInit() {
    int updateChoice = ShowMessage("初始化", "是否拉取最新版本？\n\n【是】：从 GitHub 拉取最新版本后初始化\n【否】：直接使用当前代码初始化", MB_YESNOCANCEL | MB_ICONQUESTION);
    
    if (updateChoice == IDCANCEL) return;
    
    if (updateChoice == IDYES) {
        ShowMessage("检查更新", "正在检查最新版本...", MB_ICONINFORMATION);
        
        std::string response = HttpGet(GITHUB_API_URL, GITHUB_RELEASES_PATH);
        if (response.empty()) {
            int retry = ShowMessage("错误", "无法连接到 GitHub API，请检查网络连接。\n\n是否继续使用当前代码初始化？", MB_YESNO | MB_ICONWARNING);
            if (retry != IDYES) return;
        } else {
            size_t releaseStart = response.find('{');
            if (releaseStart == std::string::npos) {
                int retry = ShowMessage("错误", "无法解析 GitHub API 响应。\n\n是否继续使用当前代码初始化？", MB_YESNO | MB_ICONWARNING);
                if (retry != IDYES) return;
            } else {
                std::string firstRelease = response.substr(releaseStart);
                size_t releaseEnd = firstRelease.find("},");
                if (releaseEnd != std::string::npos) {
                    firstRelease = firstRelease.substr(0, releaseEnd + 1);
                }
                
                std::string zipUrl = ParseJsonString(firstRelease, "zipball_url");
                std::string tagName = ParseJsonString(firstRelease, "tag_name");
                
                if (zipUrl.empty()) {
                    int retry = ShowMessage("错误", "无法获取下载链接。\n\n是否继续使用当前代码初始化？", MB_YESNO | MB_ICONWARNING);
                    if (retry != IDYES) return;
                } else {
                    std::string mirrorUrl = MIRROR_BASE_URL + zipUrl;
                    
                    std::string msg = "发现最新版本: " + tagName + "\n\n是否立即下载更新？\n\n下载源: " + mirrorUrl;
                    int result = ShowMessage("发现更新", msg, MB_YESNO | MB_ICONQUESTION);
                    
                    if (result == IDYES) {
                        if (!UpdateFromRelease(mirrorUrl)) {
                            int retry = ShowMessage("更新失败", "更新失败，是否继续使用当前代码初始化？", MB_YESNO | MB_ICONWARNING);
                            if (retry != IDYES) return;
                        } else {
                            ShowMessage("成功", "更新完成！", MB_ICONINFORMATION);
                        }
                    }
                }
            }
        }
    }
    
    if (RunCommand("where uv") != 0) {
        ShowMessage("提示", "未检测到 uv，正在通过国内代理自动安装...", MB_ICONINFORMATION);
        if (RunCommand("powershell -ExecutionPolicy ByPass -NoProfile -Command \"irm https://astral.sh/uv/install.ps1 | iex\"") != 0) {
            ShowMessage("错误", "uv 安装失败。可能是 GitHub 代理失效，请尝试手动安装 uv。", MB_ICONERROR); return;
        }
        RefreshEnvironment();
    }
    
    ShowMessage("提示", "即将弹出黑框执行 uv sync...\n(Python解释器和依赖包均使用国内镜像加速)", MB_ICONINFORMATION);
    
    HANDLE hProcess = NULL;
    if (ExecuteCommand("uv sync", CREATE_NEW_CONSOLE, false, &hProcess)) {
        WaitForSingleObject(hProcess, INFINITE);
        DWORD exitCode; GetExitCodeProcess(hProcess, &exitCode);
        CloseHandle(hProcess);
        if (exitCode == 0) ShowMessage("成功", "环境初始化 完成。", MB_ICONINFORMATION);
        else ShowMessage("警告", "uv sync 执行异常，请查看弹出的黑框日志。", MB_ICONWARNING);
    } else { ShowMessage("错误", "无法执行 uv sync。", MB_ICONERROR); }
}

DWORD RunCommand(const std::string& cmd, bool isProtected) {
    HANDLE hProcess = NULL;
    if (!ExecuteCommand(cmd, CREATE_NO_WINDOW, isProtected, &hProcess)) return GetLastError();
    WaitForSingleObject(hProcess, INFINITE);
    DWORD exitCode = 0; GetExitCodeProcess(hProcess, &exitCode);
    CloseHandle(hProcess);
    return exitCode;
}

void RefreshEnvironment() { SendMessageTimeout(HWND_BROADCAST, WM_SETTINGCHANGE, 0, (LPARAM)"Environment", SMTO_ABORTIFHUNG, 5000, NULL); }

void WorkerThread() {
    if (RunCommand("where uv") != 0) {
        if (RunCommand("powershell -ExecutionPolicy ByPass -NoProfile -Command \"irm https://astral.sh/uv/install.ps1 | iex\"") != 0) return;
        RefreshEnvironment();
    }
    if (RunCommand("uv sync", true) != 0) return;

    std::string serverCmd = "uv run python manage.py runserver " + g_Port;
    while (WaitForSingleObject(g_ServiceStopEvent, 0) == WAIT_TIMEOUT) {
        HANDLE hProcess = NULL;
        if (ExecuteCommand(serverCmd, CREATE_NO_WINDOW, true, &hProcess)) {
            HANDLE handles[2] = { hProcess, g_ServiceStopEvent };
            WaitForMultipleObjects(2, handles, FALSE, INFINITE);
            CloseHandle(hProcess);
        }
        if (WaitForSingleObject(g_ServiceStopEvent, 0) == WAIT_TIMEOUT) Sleep(3000);
    }
}

void ServiceCtrlHandler(DWORD CtrlCode) {
    if (CtrlCode == SERVICE_CONTROL_STOP) { g_ServiceStatus.dwCurrentState = SERVICE_STOP_PENDING; SetServiceStatus(g_StatusHandle, &g_ServiceStatus); SetEvent(g_ServiceStopEvent); }
}

void ServiceMain(DWORD argc, LPTSTR* argv) {
    g_StatusHandle = RegisterServiceCtrlHandlerA(SERVICE_NAME, ServiceCtrlHandler);
    g_ServiceStopEvent = CreateEvent(NULL, TRUE, FALSE, NULL);
    g_ServiceStatus.dwServiceType = SERVICE_WIN32_OWN_PROCESS; g_ServiceStatus.dwCurrentState = SERVICE_START_PENDING;
    SetServiceStatus(g_StatusHandle, &g_ServiceStatus);
    g_ServiceStatus.dwCurrentState = SERVICE_RUNNING;
    SetServiceStatus(g_StatusHandle, &g_ServiceStatus);
    WorkerThread();
    CloseHandle(g_ServiceStopEvent);
    g_ServiceStatus.dwCurrentState = SERVICE_STOPPED;
    SetServiceStatus(g_StatusHandle, &g_ServiceStatus);
}

int main(int argc, char* argv[]) {
    if (argc > 1 && std::string(argv[1]) == "--run") {
        g_Port = (argc > 2) ? argv[2] : "8000";
        SERVICE_TABLE_ENTRYA ServiceTable[] = { {(LPSTR)SERVICE_NAME, (LPSERVICE_MAIN_FUNCTIONA)ServiceMain}, {NULL, NULL} };
        StartServiceCtrlDispatcherA(ServiceTable);
        return 0;
    }

    std::string action = "start"; std::string port = "8000"; std::vector<std::string> passthrough_args;
    if (argc > 1) {
        std::string arg1 = argv[1];
        if (IsNumber(arg1)) { port = arg1; }
        else if (arg1 == "start" || arg1 == "restart") { action = arg1; if (argc > 2 && IsNumber(argv[2])) port = argv[2]; }
        else if (arg1 == "stop" || arg1 == "init" || arg1 == "update") { action = arg1; }
        else { action = "passthrough"; passthrough_args.assign(argv + 1, argv + argc); }
    }

    if (action == "stop") StopAndUninstallService();
    else if (action == "start" || action == "restart") HandleControlCommand(action, port);
    else if (action == "init") HandleInit();
    else if (action == "update") HandleUpdate();
    else if (action == "passthrough") HandlePassthrough(passthrough_args);

    return 0;
}
