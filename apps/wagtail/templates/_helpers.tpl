{{- define "wagtail.env" }}
- name: DATABASE_URL
  valueFrom:
    secretKeyRef:
      name: {{ .Values.envSecrets.database.existingSecret }}
      key: {{ .Values.envSecrets.database.urlKey }}
- name: DJANGO_SECRET_KEY
  valueFrom:
    secretKeyRef:
      name: {{ .Values.envSecrets.django.existingSecret }}
      key: {{ .Values.envSecrets.django.secretKey }}
- name: DJANGO_ALLOWED_HOSTS
  value: {{ .Values.env.APPLICATION_HOSTS | quote }}
- name: WAGTAILADMIN_BASE_URL
  value: {{ .Values.env.APPLICATION_BASE_URL | quote }}
- name: OIDC_PROVIDER_ID
  value: {{ .Values.env.OIDC_PROVIDER_ID | quote }}
- name: OIDC_ISSUER
  value: {{ .Values.env.OIDC_ISSUER | quote }}
- name: OIDC_CLIENT_NAME
  value: {{ .Values.env.OIDC_CLIENT_NAME | quote }}
- name: OIDC_CLIENT_ID
  valueFrom:
    secretKeyRef:
      name: {{ .Values.envSecrets.oidc.existingSecret }}
      key: {{ .Values.envSecrets.oidc.clientIdKey }}
- name: OIDC_CLIENT_SECRET
  valueFrom:
    secretKeyRef:
      name: {{ .Values.envSecrets.oidc.existingSecret }}
      key: {{ .Values.envSecrets.oidc.clientSecretKey }}
- name: OIDC_SCOPE
  value: {{ .Values.env.OIDC_SCOPE | quote }}
- name: OIDC_GROUPS_ATTRIBUTE
  value: {{ .Values.env.OIDC_GROUPS_ATTRIBUTE | quote }}
- name: OIDC_LOGOUT_REDIRECT_URL
  value: {{ .Values.env.OIDC_LOGOUT_REDIRECT_URL | quote }}
{{- end }}
