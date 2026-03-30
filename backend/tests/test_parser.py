import pytest
from models.schemas import ChangeType, Ecosystem
from parsers.dependency_parser import (
    parse_requirements_txt,
    parse_package_json,
    parse_go_mod,
    compute_deltas,
)

def test_parse_requirements():
    content = """
requests==2.31.0
urllib3>=1.26.0
flask~=2.0.0
bare-package
# comment
    """
    deps = parse_requirements_txt(content)
    assert len(deps) == 4
    
    deps_dict = {d.name: d for d in deps}
    assert deps_dict["requests"].version == "2.31.0"
    assert deps_dict["urllib3"].version == "1.26.0"
    assert deps_dict["flask"].version == "2.0.0"
    assert deps_dict["bare-package"].version == "*"
    assert all(d.ecosystem == Ecosystem.PYPI for d in deps)


def test_parse_package_json():
    content = """{
        "dependencies": {
            "react": "^18.2.0",
            "lodash": "~4.17.21"
        },
        "devDependencies": {
            "jest": "29.5.0",
            "typescript": ">=5.0.0"
        }
    }"""
    deps = parse_package_json(content)
    assert len(deps) == 4
    
    deps_dict = {d.name: d for d in deps}
    assert deps_dict["react"].version == "18.2.0"
    assert deps_dict["lodash"].version == "4.17.21"
    assert deps_dict["jest"].version == "29.5.0"
    assert deps_dict["typescript"].version == "5.0.0"
    assert all(d.ecosystem == Ecosystem.NPM for d in deps)


def test_parse_go_mod():
    content = """module github.com/user/project

go 1.21

require (
    github.com/gin-gally/gin v1.9.1
    golang.org/x/crypto v0.14.0 // indirect
)
require gorm.io/gorm v1.25.5
"""
    deps = parse_go_mod(content)
    assert len(deps) == 3
    
    deps_dict = {d.name: d for d in deps}
    assert deps_dict["github.com/gin-gally/gin"].version == "1.9.1"
    assert deps_dict["golang.org/x/crypto"].version == "0.14.0"
    assert deps_dict["gorm.io/gorm"].version == "1.25.5"
    assert all(d.ecosystem == Ecosystem.GO for d in deps)


def test_compute_deltas():
    base_content = """requests==2.30.0
urllib3==1.25.0
old-pkg==1.0.0"""
    head_content = """requests==2.30.1
urllib3==2.0.0
new-pkg==1.0.0"""
    
    base_deps = parse_requirements_txt(base_content)
    head_deps = parse_requirements_txt(head_content)
    
    deltas = compute_deltas(base_deps, head_deps)
    assert len(deltas) == 4
    
    deltas_dict = {d.package_name: d for d in deltas}
    
    # Patch bump
    assert deltas_dict["requests"].change_type == ChangeType.PATCH
    assert deltas_dict["requests"].old.version == "2.30.0"
    assert deltas_dict["requests"].new.version == "2.30.1"
    
    # Major bump
    assert deltas_dict["urllib3"].change_type == ChangeType.MAJOR
    assert deltas_dict["urllib3"].old.version == "1.25.0"
    assert deltas_dict["urllib3"].new.version == "2.0.0"
    
    # New package
    assert deltas_dict["new-pkg"].change_type == ChangeType.NEW
    assert deltas_dict["new-pkg"].old is None
    
    # Removed package
    assert deltas_dict["old-pkg"].change_type == ChangeType.REMOVED
    assert deltas_dict["old-pkg"].new is None
