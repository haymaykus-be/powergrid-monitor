"""Prometheus metrics API routes."""
from fastapi import APIRouter
from fastapi.responses import Response
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST

router = APIRouter(tags=["metrics"])


def filter_custom_metrics():
    """Generate metrics output with only custom application metrics."""
    # Get all metrics as string
    all_metrics = generate_latest().decode('utf-8')
    
    # Filter to only custom metrics (exclude Python built-in metrics)
    custom_metric_prefixes = [
        'mqtt_ingest',
        'validation_errors',
        'batch_insert',
        'anomaly_detection',
        'maintenance_prediction'
    ]
    
    filtered_lines = []
    include_current_metric = False
    current_metric_name = None
    
    for line in all_metrics.split('\n'):
        # Check if this is a metric definition line
        if line.startswith('# HELP '):
            # Extract metric name (format: # HELP metric_name description)
            parts = line.split()
            if len(parts) >= 3:
                current_metric_name = parts[2]
                # Check if it's a custom metric
                include_current_metric = any(current_metric_name.startswith(prefix) for prefix in custom_metric_prefixes)
                if include_current_metric:
                    filtered_lines.append(line)
        elif line.startswith('# TYPE '):
            # Type definition - include if it's a custom metric
            if include_current_metric:
                filtered_lines.append(line)
        elif line.strip():
            # Metric value line - include if it belongs to a custom metric
            if include_current_metric and current_metric_name:
                # Check if line starts with the metric name (could have labels)
                if line.startswith(current_metric_name):
                    filtered_lines.append(line)
        elif not line.strip():
            # Empty line - add spacing between metric groups
            if filtered_lines and filtered_lines[-1].strip():
                filtered_lines.append('')
    
    return '\n'.join(filtered_lines).strip() + '\n'


@router.get("/metrics")
async def metrics():
    """Prometheus metrics endpoint - all metrics including Python built-ins."""
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


@router.get("/metrics/custom")
async def custom_metrics():
    """Prometheus metrics endpoint - only custom application metrics."""
    filtered_output = filter_custom_metrics()
    return Response(filtered_output, media_type=CONTENT_TYPE_LATEST)

