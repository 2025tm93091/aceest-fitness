#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# deploy.sh — deploy ACEest to Kubernetes with a chosen release strategy.
#
#   Usage: scripts/deploy.sh <strategy> <dockerhub-user> <new-tag> [stable-tag]
#     strategy   : rolling | blue-green | canary | ab-testing | shadow
#     new-tag    : image tag being released            (e.g. v2 or v15)
#     stable-tag : tag currently trusted in production (default: v1)
#
#   Rollback:    scripts/deploy.sh rollback <dockerhub-user> <strategy>
#
# Used by the Jenkins "Deploy to Kubernetes" stage; also runnable by hand.
# ---------------------------------------------------------------------------
set -euo pipefail

STRATEGY="${1:?strategy required}"
USER_NS="${2:?dockerhub user required}"
NEW_TAG="${3:-v2}"
STABLE_TAG="${4:-v1}"
NS=aceest
IMG="${USER_NS}/aceest-fitness"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"

apply() {  # apply a manifest after substituting the Docker Hub user
  sed "s#DOCKERHUB_USER#${USER_NS}#g" "$1" | kubectl apply -f -
}
wait_ready() {
  kubectl -n "$NS" rollout status "deployment/$1" --timeout=180s
}
current_color() {
  kubectl -n "$NS" get svc aceest-bluegreen -o jsonpath='{.spec.selector.color}' 2>/dev/null || echo blue
}

kubectl apply -f "$ROOT/k8s/namespace.yaml"

case "$STRATEGY" in
  rolling)
    apply "$ROOT/k8s/rolling-update/rolling.yaml"
    kubectl -n "$NS" set image deployment/aceest-rolling "app=${IMG}:${NEW_TAG}"
    if ! wait_ready aceest-rolling; then
      echo "Rollout failed -> rolling back"; kubectl -n "$NS" rollout undo deployment/aceest-rolling; exit 1
    fi
    ;;

  blue-green)
    # First run creates both colours; afterwards only the idle colour is updated.
    kubectl -n "$NS" get svc aceest-bluegreen >/dev/null 2>&1 || apply "$ROOT/k8s/blue-green/blue-green.yaml"
    LIVE=$(current_color); IDLE=$([ "$LIVE" = blue ] && echo green || echo blue)
    echo "Live colour: $LIVE  ->  releasing ${NEW_TAG} to $IDLE"
    kubectl -n "$NS" set image "deployment/aceest-${IDLE}" "app=${IMG}:${NEW_TAG}"
    wait_ready "aceest-${IDLE}"
    kubectl -n "$NS" patch svc aceest-bluegreen \
      -p "{\"spec\":{\"selector\":{\"app\":\"aceest-bg\",\"color\":\"${IDLE}\"}}}"
    echo "Traffic switched to $IDLE (previous colour $LIVE kept for instant rollback)"
    ;;

  canary)
    apply "$ROOT/k8s/canary/canary.yaml"
    kubectl -n "$NS" set image deployment/aceest-stable "app=${IMG}:${STABLE_TAG}"
    kubectl -n "$NS" set image deployment/aceest-canary "app=${IMG}:${NEW_TAG}"
    wait_ready aceest-stable; wait_ready aceest-canary
    echo "Canary ${NEW_TAG} receiving 20% of canary.aceest.local traffic"
    ;;

  ab-testing)
    apply "$ROOT/k8s/ab-testing/ab-testing.yaml"
    kubectl -n "$NS" set image deployment/aceest-version-a "app=${IMG}:${STABLE_TAG}"
    kubectl -n "$NS" set image deployment/aceest-version-b "app=${IMG}:${NEW_TAG}"
    wait_ready aceest-version-a; wait_ready aceest-version-b
    echo "A/B live: header 'X-Variant: B' or cookie ab_variant_b=always -> ${NEW_TAG}"
    ;;

  shadow)
    apply "$ROOT/k8s/shadow/shadow.yaml"
    kubectl -n "$NS" set image deployment/aceest-production "app=${IMG}:${STABLE_TAG}"
    kubectl -n "$NS" set image deployment/aceest-shadow "app=${IMG}:${NEW_TAG}"
    wait_ready aceest-production; wait_ready aceest-shadow
    echo "Shadow ${NEW_TAG} receiving a mirrored copy of shadow.aceest.local traffic"
    ;;

  rollback)
    TARGET="${3:?strategy to roll back required}"
    case "$TARGET" in
      rolling)    kubectl -n "$NS" rollout undo deployment/aceest-rolling ;;
      blue-green) LIVE=$(current_color); PREV=$([ "$LIVE" = blue ] && echo green || echo blue)
                  kubectl -n "$NS" patch svc aceest-bluegreen \
                    -p "{\"spec\":{\"selector\":{\"app\":\"aceest-bg\",\"color\":\"${PREV}\"}}}"
                  echo "Traffic switched back to $PREV" ;;
      canary)     kubectl -n "$NS" scale deployment/aceest-canary --replicas=0 ;;
      ab-testing) kubectl -n "$NS" delete ingress aceest-ab-b --ignore-not-found ;;
      shadow)     kubectl -n "$NS" scale deployment/aceest-shadow --replicas=0 ;;
      *) echo "unknown strategy $TARGET"; exit 2 ;;
    esac
    ;;

  *) echo "unknown strategy: $STRATEGY"; exit 2 ;;
esac

kubectl -n "$NS" get deploy,svc,ingress -o wide
