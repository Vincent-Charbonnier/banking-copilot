{{/*
Expand the name of the chart.
*/}}
{{- define "retail-banking-copilot.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" -}}
{{- end }}

{{/*
Create a default fully qualified app name.
*/}}
{{- define "retail-banking-copilot.fullname" -}}
{{- if .Values.fullnameOverride -}}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" -}}
{{- else -}}
{{- $name := default .Chart.Name .Values.nameOverride -}}
{{- if contains $name .Release.Name -}}
{{- .Release.Name | trunc 63 | trimSuffix "-" -}}
{{- else -}}
{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" -}}
{{- end -}}
{{- end -}}
{{- end }}

{{/*
Create chart name and version as used by the chart label.
*/}}
{{- define "retail-banking-copilot.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" -}}
{{- end }}

{{/*
Common labels.
*/}}
{{- define "retail-banking-copilot.labels" -}}
helm.sh/chart: {{ include "retail-banking-copilot.chart" . }}
{{ include "retail-banking-copilot.selectorLabels" . }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{/*
Selector labels.
*/}}
{{- define "retail-banking-copilot.selectorLabels" -}}
app.kubernetes.io/name: {{ include "retail-banking-copilot.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{/*
Service account name.
*/}}
{{- define "retail-banking-copilot.serviceAccountName" -}}
{{- if .Values.serviceAccount.create -}}
{{- default (include "retail-banking-copilot.fullname" .) .Values.serviceAccount.name }}
{{- else -}}
{{- default "default" .Values.serviceAccount.name }}
{{- end -}}
{{- end }}

{{/*
App secret name.
*/}}
{{- define "retail-banking-copilot.secretName" -}}
{{- if .Values.llm.existingSecret -}}
{{- .Values.llm.existingSecret -}}
{{- else -}}
{{- printf "%s-llm" (include "retail-banking-copilot.fullname" .) -}}
{{- end -}}
{{- end }}
