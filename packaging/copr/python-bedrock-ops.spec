%global pypi_name bedrock-ops
%global pypi_module bedrock_ops

Name:           python-%{pypi_name}
Version:        0.1.0
Release:        1%{?dist}
Summary:        Production-grade boto3 toolkit for AWS Bedrock

License:        Apache-2.0
URL:            https://github.com/MukundaKatta/%{pypi_name}
Source0:        https://github.com/MukundaKatta/%{pypi_name}/releases/download/v%{version}/%{pypi_module}-%{version}.tar.gz

BuildArch:      noarch
BuildRequires:  python3-devel
BuildRequires:  python3dist(uv-build)

%global _description %{expand:
Closes the gaps every team rebuilds when running AWS Bedrock in production:
case-insensitive throttle retry (so botocore actually retries lowercase
throttlingException returned by some Bedrock paths), per-model timeouts,
full TokenUsage including cacheReadInputTokens / cacheWriteInputTokens
(so prompt-cache hit rate is measurable), capability lookup table, typed
exception mapping, and a Guardrails wrapper that redacts violating PII
before any logger sees it.}

%description %_description

%package -n python3-%{pypi_name}
Summary:        %{summary}
Requires:       python3-boto3 >= 1.35
Requires:       python3-botocore >= 1.35

%description -n python3-%{pypi_name} %_description

%prep
%autosetup -p1 -n %{pypi_module}-%{version}

%generate_buildrequires
%pyproject_buildrequires

%build
%pyproject_wheel

%install
%pyproject_install
%pyproject_save_files %{pypi_module}

%check
%pyproject_check_import

%files -n python3-%{pypi_name} -f %{pyproject_files}
%license LICENSE
%doc README.md CHANGELOG.md

%changelog
* Sat May 09 2026 Mukunda Katta <mukunda.vjcs6@gmail.com> - 0.1.0-1
- Initial Fedora packaging
