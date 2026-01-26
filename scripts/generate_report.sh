#!/bin/bash
# generate_report.sh - Generate verification report
#
# Usage: ./scripts/generate_report.sh [--html] [--json] [--badge]

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

REPORTS_DIR="${PROJECT_ROOT}/reports"
OUTPUT_DIR="${PROJECT_ROOT}/public"

# Parse arguments
GENERATE_HTML=false
GENERATE_JSON=true
GENERATE_BADGE=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --html)
            GENERATE_HTML=true
            shift
            ;;
        --json)
            GENERATE_JSON=true
            shift
            ;;
        --badge)
            GENERATE_BADGE=true
            shift
            ;;
        --all)
            GENERATE_HTML=true
            GENERATE_JSON=true
            GENERATE_BADGE=true
            shift
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

mkdir -p "$OUTPUT_DIR"

echo "Generating verification report..."

# Collect all test results
collect_results() {
    local total_passed=0
    local total_failed=0
    local total_skipped=0

    if [ -f "${REPORTS_DIR}/summary.json" ]; then
        total_passed=$(jq -r '.passed // 0' "${REPORTS_DIR}/summary.json")
        total_failed=$(jq -r '.failed // 0' "${REPORTS_DIR}/summary.json")
        total_skipped=$(jq -r '.skipped // 0' "${REPORTS_DIR}/summary.json")
    fi

    echo "$total_passed $total_failed $total_skipped"
}

# Generate JSON report
if [ "$GENERATE_JSON" = true ]; then
    echo "Generating JSON report..."

    read -r passed failed skipped <<< "$(collect_results)"
    total=$((passed + failed + skipped))
    pass_rate=0
    if [ $total -gt 0 ]; then
        pass_rate=$(echo "scale=1; $passed * 100 / $total" | bc)
    fi

    cat > "${OUTPUT_DIR}/verification-report.json" << EOF
{
  "generated_at": "$(date -Iseconds)",
  "repository": "geode-examples",
  "summary": {
    "total_tests": $total,
    "passed": $passed,
    "failed": $failed,
    "skipped": $skipped,
    "pass_rate": $pass_rate
  },
  "claims_verified": {
    "total": 0,
    "verified": 0,
    "failed": 0,
    "pending": 0
  },
  "categories": {
    "gql_compliance": {
      "status": "pending",
      "tests": 0,
      "passed": 0
    },
    "performance": {
      "status": "pending",
      "tests": 0,
      "passed": 0
    },
    "security": {
      "status": "pending",
      "tests": 0,
      "passed": 0
    },
    "clients": {
      "status": "pending",
      "tests": 0,
      "passed": 0
    }
  }
}
EOF
    echo "  -> ${OUTPUT_DIR}/verification-report.json"
fi

# Generate HTML report
if [ "$GENERATE_HTML" = true ]; then
    echo "Generating HTML report..."

    read -r passed failed skipped <<< "$(collect_results)"
    total=$((passed + failed + skipped))

    cat > "${OUTPUT_DIR}/index.html" << 'HTMLEOF'
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Geode Examples - Verification Report</title>
    <style>
        :root {
            --primary: #2563eb;
            --success: #16a34a;
            --danger: #dc2626;
            --warning: #ca8a04;
            --bg: #f8fafc;
            --card-bg: #ffffff;
            --text: #1e293b;
        }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: var(--bg);
            color: var(--text);
            margin: 0;
            padding: 2rem;
            line-height: 1.6;
        }
        .container { max-width: 1200px; margin: 0 auto; }
        h1 { color: var(--primary); }
        .card {
            background: var(--card-bg);
            border-radius: 8px;
            box-shadow: 0 1px 3px rgba(0,0,0,0.1);
            padding: 1.5rem;
            margin-bottom: 1.5rem;
        }
        .stats { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 1rem; }
        .stat {
            text-align: center;
            padding: 1rem;
            border-radius: 8px;
            background: var(--bg);
        }
        .stat-value { font-size: 2.5rem; font-weight: bold; }
        .stat-label { font-size: 0.875rem; color: #64748b; }
        .success { color: var(--success); }
        .danger { color: var(--danger); }
        .warning { color: var(--warning); }
        table { width: 100%; border-collapse: collapse; }
        th, td { padding: 0.75rem; text-align: left; border-bottom: 1px solid #e2e8f0; }
        th { background: var(--bg); font-weight: 600; }
        .badge {
            display: inline-block;
            padding: 0.25rem 0.5rem;
            border-radius: 4px;
            font-size: 0.75rem;
            font-weight: 600;
        }
        .badge-success { background: #dcfce7; color: var(--success); }
        .badge-danger { background: #fee2e2; color: var(--danger); }
        .badge-warning { background: #fef9c3; color: var(--warning); }
    </style>
</head>
<body>
    <div class="container">
        <h1>Geode Examples - Verification Report</h1>
        <p>Generated: <strong id="timestamp"></strong></p>

        <div class="card">
            <h2>Summary</h2>
            <div class="stats">
                <div class="stat">
                    <div class="stat-value" id="total">-</div>
                    <div class="stat-label">Total Tests</div>
                </div>
                <div class="stat">
                    <div class="stat-value success" id="passed">-</div>
                    <div class="stat-label">Passed</div>
                </div>
                <div class="stat">
                    <div class="stat-value danger" id="failed">-</div>
                    <div class="stat-label">Failed</div>
                </div>
                <div class="stat">
                    <div class="stat-value warning" id="skipped">-</div>
                    <div class="stat-label">Skipped</div>
                </div>
            </div>
        </div>

        <div class="card">
            <h2>Claim Verification Status</h2>
            <table>
                <thead>
                    <tr>
                        <th>Category</th>
                        <th>Claims</th>
                        <th>Verified</th>
                        <th>Status</th>
                    </tr>
                </thead>
                <tbody id="claims-table">
                    <tr>
                        <td>GQL Compliance</td>
                        <td>5</td>
                        <td>0</td>
                        <td><span class="badge badge-warning">Pending</span></td>
                    </tr>
                    <tr>
                        <td>Performance</td>
                        <td>8</td>
                        <td>0</td>
                        <td><span class="badge badge-warning">Pending</span></td>
                    </tr>
                    <tr>
                        <td>Security</td>
                        <td>8</td>
                        <td>0</td>
                        <td><span class="badge badge-warning">Pending</span></td>
                    </tr>
                    <tr>
                        <td>Features</td>
                        <td>8</td>
                        <td>0</td>
                        <td><span class="badge badge-warning">Pending</span></td>
                    </tr>
                    <tr>
                        <td>Client Libraries</td>
                        <td>5</td>
                        <td>0</td>
                        <td><span class="badge badge-warning">Pending</span></td>
                    </tr>
                </tbody>
            </table>
        </div>

        <div class="card">
            <h2>About</h2>
            <p>This report verifies claims made in the <a href="https://geodedb.com">Geode documentation</a> against actual black-box testing of the database.</p>
            <p><a href="verification-report.json">Download JSON Report</a></p>
        </div>
    </div>

    <script>
        fetch('verification-report.json')
            .then(r => r.json())
            .then(data => {
                document.getElementById('timestamp').textContent = new Date(data.generated_at).toLocaleString();
                document.getElementById('total').textContent = data.summary.total_tests;
                document.getElementById('passed').textContent = data.summary.passed;
                document.getElementById('failed').textContent = data.summary.failed;
                document.getElementById('skipped').textContent = data.summary.skipped;
            })
            .catch(err => console.error('Failed to load report:', err));
    </script>
</body>
</html>
HTMLEOF
    echo "  -> ${OUTPUT_DIR}/index.html"
fi

# Generate badge
if [ "$GENERATE_BADGE" = true ]; then
    echo "Generating badge..."

    read -r passed failed skipped <<< "$(collect_results)"
    total=$((passed + failed))

    if [ $total -eq 0 ]; then
        label="pending"
        color="yellow"
        value="0%"
    else
        pct=$((passed * 100 / total))
        value="${pct}%"
        if [ $pct -ge 90 ]; then
            color="brightgreen"
            label="passing"
        elif [ $pct -ge 70 ]; then
            color="yellow"
            label="partial"
        else
            color="red"
            label="failing"
        fi
    fi

    # Generate SVG badge
    cat > "${OUTPUT_DIR}/verification-badge.svg" << SVGEOF
<svg xmlns="http://www.w3.org/2000/svg" width="140" height="20">
  <linearGradient id="b" x2="0" y2="100%">
    <stop offset="0" stop-color="#bbb" stop-opacity=".1"/>
    <stop offset="1" stop-opacity=".1"/>
  </linearGradient>
  <mask id="a"><rect width="140" height="20" rx="3" fill="#fff"/></mask>
  <g mask="url(#a)">
    <path fill="#555" d="M0 0h75v20H0z"/>
    <path fill="${color}" d="M75 0h65v20H75z"/>
    <path fill="url(#b)" d="M0 0h140v20H0z"/>
  </g>
  <g fill="#fff" text-anchor="middle" font-family="DejaVu Sans,Verdana,sans-serif" font-size="11">
    <text x="37.5" y="15" fill="#010101" fill-opacity=".3">verification</text>
    <text x="37.5" y="14">verification</text>
    <text x="107" y="15" fill="#010101" fill-opacity=".3">${value}</text>
    <text x="107" y="14">${value}</text>
  </g>
</svg>
SVGEOF
    echo "  -> ${OUTPUT_DIR}/verification-badge.svg"
fi

echo ""
echo "Report generation complete!"
echo "View at: ${OUTPUT_DIR}/index.html"
