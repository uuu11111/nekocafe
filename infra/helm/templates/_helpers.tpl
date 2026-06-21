{{/* 通用标签：遵循 Kubernetes 推荐标签集 */}}
{{- define "nekocafe.labels" -}}
app.kubernetes.io/name: {{ .Release.Name }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/version: {{ .Values.image.tag | default .Chart.AppVersion | quote }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
app.kubernetes.io/part-of: nekocafe
helm.sh/chart: {{ .Chart.Name }}-{{ .Chart.Version }}
{{- end -}}

{{/* 选择器标签：稳定/金丝雀共用 app，再用 track 区分 */}}
{{- define "nekocafe.selectorLabels" -}}
app: {{ .Release.Name }}
{{- end -}}

{{/*
共享 Pod 规格。调用方传 dict：
  root  -> 顶层 .（取 Values/Release/Chart）
  tag   -> 该 track 用的镜像 tag
安全基线：非 root、只读根文件系统、丢弃全部 capabilities、不挂 SA token。
*/}}
{{- define "nekocafe.podSpec" -}}
{{- $root := .root -}}
automountServiceAccountToken: false
securityContext:
  runAsNonRoot: true
  runAsUser: 10001
  fsGroup: 10001
  seccompProfile:
    type: RuntimeDefault
containers:
  - name: app
    image: "{{ $root.Values.image.repository }}:{{ .tag }}"
    imagePullPolicy: {{ $root.Values.image.pullPolicy }}
    ports:
      - name: http
        containerPort: 8080
    envFrom:
      - configMapRef:
          name: {{ $root.Release.Name }}-config
      {{- if $root.Values.existingSecret }}
      - secretRef:
          name: {{ $root.Values.existingSecret }}
      {{- end }}
    livenessProbe:
      httpGet:
        path: /healthz
        port: http
      initialDelaySeconds: 10
      periodSeconds: 15
      timeoutSeconds: 3
    readinessProbe:
      httpGet:
        path: /readyz
        port: http
      initialDelaySeconds: 5
      periodSeconds: 10
      timeoutSeconds: 3
    resources:
      {{- toYaml $root.Values.resources | nindent 6 }}
    securityContext:
      allowPrivilegeEscalation: false
      readOnlyRootFilesystem: true
      capabilities:
        drop:
          - ALL
    volumeMounts:
      - name: tmp
        mountPath: /tmp
volumes:
  - name: tmp
    emptyDir: {}
{{- end -}}
