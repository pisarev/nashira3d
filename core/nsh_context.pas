{ ************************************************************************** }
{                                                                            }
{ nsh_context                                                                }
{                                                                            }
{ Copyright © 2026 Yuriy Pisarev (ypisareff@outlook.com)                     }
{                                                                            }
{ ************************************************************************** }

unit nsh_context;

{$mode objfpc}{$H+}

interface

function  CtxCreate: Boolean;
procedure CtxDestroy;
function  CtxError: AnsiString;
function  CtxReady: Boolean;

function  CtxTarget(W, H: LongInt): Boolean;

function  CtxResolve: Boolean;

function  CtxSamples: LongInt;

implementation

uses
  SysUtils, GL, GLext
  {$IFDEF WINDOWS}, Windows{$ENDIF};

type
  PEGLint = ^LongInt;

var
  FError : AnsiString = '';
  FReady : Boolean = False;
  FFbo   : GLuint = 0;
  FColor : GLuint = 0;
  FDepth : GLuint = 0;
  FResFbo   : GLuint = 0;
  FResColor : GLuint = 0;
  FSamples  : LongInt = 0;
  FTgtW  : LongInt = 0;
  FTgtH  : LongInt = 0;

{$IFDEF WINDOWS}
const
  WGL_CONTEXT_MAJOR_VERSION_ARB    = $2091;
  WGL_CONTEXT_MINOR_VERSION_ARB    = $2092;
  WGL_CONTEXT_PROFILE_MASK_ARB     = $9126;
  WGL_CONTEXT_CORE_PROFILE_BIT_ARB = $00000001;
  CLASS_NAME = 'Nashira3DHiddenGL';

function wglCreateContext(dc: HDC): HGLRC; stdcall; external 'opengl32.dll';
function wglMakeCurrent(dc: HDC; rc: HGLRC): LongBool; stdcall; external 'opengl32.dll';
function wglDeleteContext(rc: HGLRC): LongBool; stdcall; external 'opengl32.dll';
function wglGetProcAddress(name: PAnsiChar): Pointer; stdcall; external 'opengl32.dll';

type
  TCreateCtxAttribs = function(dc: HDC; share: HGLRC; attribs: PInteger): HGLRC; stdcall;

var
  FWnd : HWND  = 0;
  FDC  : HDC   = 0;
  FRC  : HGLRC = 0;

procedure DropWindows;
begin
  if FRC <> 0 then
  begin
    wglMakeCurrent(0, 0);
    wglDeleteContext(FRC);
    FRC := 0;
  end;
  if (FDC <> 0) and (FWnd <> 0) then
  begin
    ReleaseDC(FWnd, FDC);
    FDC := 0;
  end;
  if FWnd <> 0 then
  begin
    DestroyWindow(FWnd);
    FWnd := 0;
  end;
end;

function CreateWindows: Boolean;
var
  WC      : WNDCLASS;
  PFD     : PIXELFORMATDESCRIPTOR;
  Fmt     : Integer;
  Tmp     : HGLRC;
  MakeCtx : TCreateCtxAttribs;
  Attribs : array[0..6] of Integer;
begin
  Result := False;
  FillChar(WC, SizeOf(WC), 0);
  WC.lpfnWndProc   := @DefWindowProc;
  WC.hInstance     := HInstance;
  WC.lpszClassName := CLASS_NAME;
  Windows.RegisterClass(WC);
  FWnd := CreateWindowEx(0, CLASS_NAME, '', WS_OVERLAPPED, 0, 0, 1, 1, 0, 0, HInstance, nil);
  if FWnd = 0 then
  begin
    FError := 'CreateWindowEx failed';
    Exit;
  end;
  FDC := GetDC(FWnd);
  if FDC = 0 then
  begin
    FError := 'GetDC failed'; DropWindows; Exit;
  end;
  FillChar(PFD, SizeOf(PFD), 0);
  PFD.nSize      := SizeOf(PFD);
  PFD.nVersion   := 1;
  PFD.dwFlags    := PFD_DRAW_TO_WINDOW or PFD_SUPPORT_OPENGL;
  PFD.iPixelType := PFD_TYPE_RGBA;
  PFD.cColorBits := 32;
  PFD.cDepthBits := 24;
  Fmt := ChoosePixelFormat(FDC, @PFD);
  if (Fmt = 0) or (not SetPixelFormat(FDC, Fmt, @PFD)) then
  begin
    FError := 'no suitable pixel format'; DropWindows; Exit;
  end;
  Tmp := wglCreateContext(FDC);
  if Tmp = 0 then
  begin
    FError := 'wglCreateContext failed'; DropWindows; Exit;
  end;
  wglMakeCurrent(FDC, Tmp);
  MakeCtx := TCreateCtxAttribs(wglGetProcAddress('wglCreateContextAttribsARB'));
  if MakeCtx = nil then
  begin
    FError := 'wglCreateContextAttribsARB is absent: driver has no OpenGL 3.3';
    wglMakeCurrent(0, 0); wglDeleteContext(Tmp); DropWindows; Exit;
  end;
  Attribs[0] := WGL_CONTEXT_MAJOR_VERSION_ARB;
  Attribs[1] := 3;
  Attribs[2] := WGL_CONTEXT_MINOR_VERSION_ARB;
  Attribs[3] := 3;
  Attribs[4] := WGL_CONTEXT_PROFILE_MASK_ARB;
  Attribs[5] := WGL_CONTEXT_CORE_PROFILE_BIT_ARB;
  Attribs[6] := 0;
  FRC := MakeCtx(FDC, 0, @Attribs[0]);
  wglMakeCurrent(0, 0);
  wglDeleteContext(Tmp);
  if FRC = 0 then
  begin
    FError := 'no OpenGL 3.3 core context'; DropWindows; Exit;
  end;
  if not wglMakeCurrent(FDC, FRC) then
  begin
    FError := 'wglMakeCurrent on core context failed'; DropWindows; Exit;
  end;
  Result := True;
end;
{$ENDIF}

{$IFDEF LINUX}
type
  EGLDisplay = Pointer;
  EGLSurface = Pointer;
  EGLContext = Pointer;
  EGLConfig  = Pointer;
  EGLint     = LongInt;
  EGLenum    = LongWord;
  EGLBoolean = LongWord;

const
  EGL_LIB = 'libEGL.so.1';
  EGL_FALSE                  = 0;
  EGL_NONE                   = $3038;
  EGL_OPENGL_API             = $30A2;
  EGL_SURFACE_TYPE           = $3033;
  EGL_PBUFFER_BIT            = $0001;
  EGL_RENDERABLE_TYPE        = $3040;
  EGL_OPENGL_BIT             = $0008;
  EGL_RED_SIZE               = $3024;
  EGL_GREEN_SIZE             = $3023;
  EGL_BLUE_SIZE              = $3022;
  EGL_ALPHA_SIZE             = $3021;
  EGL_DEPTH_SIZE             = $3025;
  EGL_WIDTH                  = $3057;
  EGL_HEIGHT                 = $3056;
  EGL_CONTEXT_MAJOR_VERSION  = $3098;
  EGL_CONTEXT_MINOR_VERSION  = $30FB;
  EGL_CONTEXT_PROFILE_MASK   = $30FD;
  EGL_CONTEXT_CORE_PROFILE   = $00000001;

function eglGetDisplay(id: Pointer): EGLDisplay; cdecl; external EGL_LIB;
function eglInitialize(d: EGLDisplay; out major, minor: EGLint): EGLBoolean; cdecl; external EGL_LIB;
function eglBindAPI(api: EGLenum): EGLBoolean; cdecl; external EGL_LIB;
function eglChooseConfig(d: EGLDisplay; attr: PEGLint; cfg: PPointer; size: EGLint;
  out num: EGLint): EGLBoolean; cdecl; external EGL_LIB;
function eglCreatePbufferSurface(d: EGLDisplay; c: EGLConfig;
  attr: PEGLint): EGLSurface; cdecl; external EGL_LIB;
function eglCreateContext(d: EGLDisplay; c: EGLConfig; share: EGLContext;
  attr: PEGLint): EGLContext; cdecl; external EGL_LIB;
function eglMakeCurrent(d: EGLDisplay; draw, read: EGLSurface;
  ctx: EGLContext): EGLBoolean; cdecl; external EGL_LIB;
function eglDestroyContext(d: EGLDisplay; ctx: EGLContext): EGLBoolean; cdecl; external EGL_LIB;
function eglDestroySurface(d: EGLDisplay; s: EGLSurface): EGLBoolean; cdecl; external EGL_LIB;
function eglTerminate(d: EGLDisplay): EGLBoolean; cdecl; external EGL_LIB;
function eglGetError: EGLint; cdecl; external EGL_LIB;

var
  FDpy : EGLDisplay = nil;
  FSurf : EGLSurface = nil;
  FCtx : EGLContext = nil;

procedure DropLinux;
begin
  if FDpy <> nil then
  begin
    eglMakeCurrent(FDpy, nil, nil, nil);
    if FCtx <> nil then
    begin
      eglDestroyContext(FDpy, FCtx);
      FCtx := nil;
    end;
    if FSurf <> nil then
    begin
      eglDestroySurface(FDpy, FSurf);
      FSurf := nil;
    end;
    eglTerminate(FDpy);
    FDpy := nil;
  end;
end;

function CreateLinux: Boolean;
var
  Major, Minor, Num: EGLint;
  Cfg: EGLConfig;
  CfgAttr: array[0..14] of EGLint;
  SurfAttr: array[0..4] of EGLint;
  CtxAttr: array[0..6] of EGLint;
begin
  Result := False;
  FDpy := eglGetDisplay(nil);
  if FDpy = nil then
  begin
    FError := 'eglGetDisplay gave no display';
    Exit;
  end;
  if eglInitialize(FDpy, Major, Minor) = EGL_FALSE then
  begin
    FError := 'eglInitialize failed, code ' + IntToStr(eglGetError);
    FDpy := nil;
    Exit;
  end;
  if eglBindAPI(EGL_OPENGL_API) = EGL_FALSE then
  begin
    FError := 'this EGL has no desktop OpenGL, only GLES'; DropLinux; Exit;
  end;
  CfgAttr[0]  := EGL_SURFACE_TYPE;
  CfgAttr[1]  := EGL_PBUFFER_BIT;
  CfgAttr[2]  := EGL_RENDERABLE_TYPE;
  CfgAttr[3]  := EGL_OPENGL_BIT;
  CfgAttr[4]  := EGL_RED_SIZE;
  CfgAttr[5]  := 8;
  CfgAttr[6]  := EGL_GREEN_SIZE;
  CfgAttr[7]  := 8;
  CfgAttr[8]  := EGL_BLUE_SIZE;
  CfgAttr[9]  := 8;
  CfgAttr[10] := EGL_ALPHA_SIZE;
  CfgAttr[11] := 8;
  CfgAttr[12] := EGL_DEPTH_SIZE;
  CfgAttr[13] := 24;
  CfgAttr[14] := EGL_NONE;
  if (eglChooseConfig(FDpy, @CfgAttr[0], @Cfg, 1, Num) = EGL_FALSE) or (Num < 1) then
  begin
    FError := 'no EGL config with desktop GL and a pbuffer'; DropLinux; Exit;
  end;
  SurfAttr[0] := EGL_WIDTH;
  SurfAttr[1] := 1;
  SurfAttr[2] := EGL_HEIGHT;
  SurfAttr[3] := 1;
  SurfAttr[4] := EGL_NONE;
  FSurf := eglCreatePbufferSurface(FDpy, Cfg, @SurfAttr[0]);
  if FSurf = nil then
  begin
    FError := 'eglCreatePbufferSurface failed'; DropLinux; Exit;
  end;
  CtxAttr[0] := EGL_CONTEXT_MAJOR_VERSION;
  CtxAttr[1] := 3;
  CtxAttr[2] := EGL_CONTEXT_MINOR_VERSION;
  CtxAttr[3] := 3;
  CtxAttr[4] := EGL_CONTEXT_PROFILE_MASK;
  CtxAttr[5] := EGL_CONTEXT_CORE_PROFILE;
  CtxAttr[6] := EGL_NONE;
  FCtx := eglCreateContext(FDpy, Cfg, nil, @CtxAttr[0]);
  if FCtx = nil then
  begin
    FError := 'no OpenGL 3.3 core context from EGL'; DropLinux; Exit;
  end;
  if eglMakeCurrent(FDpy, FSurf, FSurf, FCtx) = EGL_FALSE then
  begin
    FError := 'eglMakeCurrent failed'; DropLinux; Exit;
  end;
  Result := True;
end;
{$ENDIF}

function CtxCreate: Boolean;
begin
  FError := '';
  if FReady then Exit(True);
  {$IFDEF WINDOWS}
  if not CreateWindows then Exit(False);
  {$ELSE}
    {$IFDEF LINUX}
    if not CreateLinux then Exit(False);
    {$ELSE}
    FError := 'offscreen context is not implemented on this platform';
    Exit(False);
    {$ENDIF}
  {$ENDIF}
  if not Load_GL_version_3_3_CORE then
  begin
    FError := 'OpenGL 3.3 core entry points did not load';
    CtxDestroy;
    Exit(False);
  end;
  FReady := True;
  Result := True;
end;

procedure CtxDestroy;
begin
  {$IFDEF WINDOWS}
  DropWindows;
  {$ENDIF}
  {$IFDEF LINUX}
  DropLinux;
  {$ENDIF}
  FReady := False;
end;

function CtxTarget(W, H: LongInt): Boolean;
var
  Status: GLenum;
  Want: GLint;
begin
  Result := False;
  if not FReady then
  begin
    FError := 'context is not created';
    Exit;
  end;
  if (W <= 0) or (H <= 0) then
  begin
    FError := 'target size must be positive';
    Exit;
  end;
  if (FFbo <> 0) and (W = FTgtW) and (H = FTgtH) then
  begin
    glBindFramebuffer(GL_FRAMEBUFFER, FFbo);
    Exit(True);
  end;
  if FFbo <> 0 then
  begin
    glDeleteFramebuffers(1, @FFbo);
    glDeleteRenderbuffers(1, @FColor);
    glDeleteRenderbuffers(1, @FDepth);
    FFbo := 0;
    FColor := 0;
    FDepth := 0;
  end;
  if FResFbo <> 0 then
  begin
    glDeleteFramebuffers(1, @FResFbo);
    glDeleteRenderbuffers(1, @FResColor);
    FResFbo := 0;
    FResColor := 0;
  end;
  Want := 0;
  glGetIntegerv(GL_MAX_SAMPLES, @Want);
  if Want > 8 then Want := 8;
  if Want < 0 then Want := 0;
  FSamples := Want;
  glGenFramebuffers(1, @FFbo);
  glBindFramebuffer(GL_FRAMEBUFFER, FFbo);
  glGenRenderbuffers(1, @FColor);
  glBindRenderbuffer(GL_RENDERBUFFER, FColor);
  if FSamples > 1 then
    glRenderbufferStorageMultisample(GL_RENDERBUFFER, FSamples, GL_RGBA8, W, H)
  else
    glRenderbufferStorage(GL_RENDERBUFFER, GL_RGBA8, W, H);
  glFramebufferRenderbuffer(GL_FRAMEBUFFER, GL_COLOR_ATTACHMENT0, GL_RENDERBUFFER, FColor);
  glGenRenderbuffers(1, @FDepth);
  glBindRenderbuffer(GL_RENDERBUFFER, FDepth);
  if FSamples > 1 then
    glRenderbufferStorageMultisample(GL_RENDERBUFFER, FSamples, GL_DEPTH_COMPONENT24, W, H)
  else
    glRenderbufferStorage(GL_RENDERBUFFER, GL_DEPTH_COMPONENT24, W, H);
  glFramebufferRenderbuffer(GL_FRAMEBUFFER, GL_DEPTH_ATTACHMENT, GL_RENDERBUFFER, FDepth);
  Status := glCheckFramebufferStatus(GL_FRAMEBUFFER);
  if Status <> GL_FRAMEBUFFER_COMPLETE then
  begin
    FError := 'offscreen target is incomplete, status ' + IntToStr(Status);
    Exit;
  end;
  if FSamples > 1 then
  begin
    glGenFramebuffers(1, @FResFbo);
    glBindFramebuffer(GL_FRAMEBUFFER, FResFbo);
    glGenRenderbuffers(1, @FResColor);
    glBindRenderbuffer(GL_RENDERBUFFER, FResColor);
    glRenderbufferStorage(GL_RENDERBUFFER, GL_RGBA8, W, H);
    glFramebufferRenderbuffer(GL_FRAMEBUFFER, GL_COLOR_ATTACHMENT0, GL_RENDERBUFFER, FResColor);
    Status := glCheckFramebufferStatus(GL_FRAMEBUFFER);
    if Status <> GL_FRAMEBUFFER_COMPLETE then
    begin
      FError := 'resolve target is incomplete, status ' + IntToStr(Status);
      Exit;
    end;
    glBindFramebuffer(GL_FRAMEBUFFER, FFbo);
  end;
  FTgtW := W;
  FTgtH := H;
  Result := True;
end;

function CtxResolve: Boolean;
begin
  if not FReady then
  begin
    FError := 'context is not created';
    Exit(False);
  end;
  if FFbo = 0 then
  begin
    FError := 'no target to resolve';
    Exit(False);
  end;
  if FSamples <= 1 then
  begin
    glBindFramebuffer(GL_READ_FRAMEBUFFER, FFbo);
    Exit(True);
  end;
  glBindFramebuffer(GL_READ_FRAMEBUFFER, FFbo);
  glBindFramebuffer(GL_DRAW_FRAMEBUFFER, FResFbo);
  glBlitFramebuffer(0, 0, FTgtW, FTgtH, 0, 0, FTgtW, FTgtH, GL_COLOR_BUFFER_BIT, GL_NEAREST);
  glBindFramebuffer(GL_READ_FRAMEBUFFER, FResFbo);
  Result := True;
end;

function CtxSamples: LongInt;
begin
  Result := FSamples;
end;

function CtxError: AnsiString;
begin
  Result := FError;
end;

function CtxReady: Boolean;
begin
  Result := FReady;
end;

end.
