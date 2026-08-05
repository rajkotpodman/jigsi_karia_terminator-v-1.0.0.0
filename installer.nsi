!define APPNAME "Jigsi Karia Terminator"
!define COMPANYNAME "Jigsi Karia Security Grid"
!define DESCRIPTION "Cyber OSINT Gateway & Hacker Scanner v4.0"
!define VERSIONMAJOR 4
!define VERSIONMINOR 0
!define VERSIONBUILD 0
!define HELPURL "https://github.com/rajkotpodman/jigsi_karia_terminator"
!define UPDATEURL "https://github.com/rajkotpodman/jigsi_karia_terminator"
!define ABOUTURL "https://github.com/rajkotpodman/jigsi_karia_terminator"
!define INSTALLSIZE 45000

Name "${APPNAME}"
OutFile "jigsi-karia-terminator-setup.exe"
InstallDir "$PROGRAMFILES64\JigsiKariaTerminator"
RequestExecutionLevel admin

SetCompressor /SOLID lzma

Page directory
Page instfiles

UninstPage uninstConfirm
UninstPage instfiles

Section "Install"
	SetOutPath "$INSTDIR"
	File /r "*"
	
	WriteUninstaller "$INSTDIR\uninstall.exe"
	
	CreateShortCut "$SMPROGRAMS\Jigsi Karia Terminator.lnk" "$INSTDIR\build-windows.bat" "" "$INSTDIR\manifest.json" 0
	CreateShortCut "$DESKTOP\Jigsi Karia Terminator.lnk" "$INSTDIR\build-windows.bat" "" "$INSTDIR\manifest.json" 0

	WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APPNAME}" "DisplayName" "${APPNAME}"
	WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APPNAME}" "UninstallString" "$INSTDIR\uninstall.exe"
	WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APPNAME}" "QuietUninstallString" "$INSTDIR\uninstall.exe /S"
	WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APPNAME}" "Publisher" "${COMPANYNAME}"
	WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APPNAME}" "URLInfoAbout" "${HELPURL}"
	WriteRegDWORD HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APPNAME}" "NoModify" 1
	WriteRegDWORD HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APPNAME}" "NoRepair" 1
	WriteRegDWORD HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APPNAME}" "EstimatedSize" ${INSTALLSIZE}
SectionEnd

Section "Uninstall"
	RMDir /r "$INSTDIR"
	Delete "$SMPROGRAMS\Jigsi Karia Terminator.lnk"
	Delete "$DESKTOP\Jigsi Karia Terminator.lnk"
	DeleteRegKey HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APPNAME}"
SectionEnd
