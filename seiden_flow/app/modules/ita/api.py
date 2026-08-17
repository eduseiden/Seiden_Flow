from __future__ import annotations
from flask import Blueprint, jsonify, render_template, request


def create_ita_blueprint(repo, version, ingress_path_fn, timezone_name, fleet_client=None, fleet_enabled=True, fleet_refresh_seconds=30):
    bp = Blueprint('ita', __name__)

    @bp.get('/ita')
    @bp.get('/intelligence/ita')
    def portal():
        return render_template(
            'ita_portal.html',
            version=version,
            ingress_path=ingress_path_fn(),
            display_timezone=timezone_name,
            refresh_seconds=fleet_refresh_seconds,
            fleet_enabled=bool(fleet_enabled),
            fleet_configured=bool(fleet_client and fleet_client.configured),
        )

    # Compatibility aliases: Fleet is no longer a separate product surface.
    # Old bookmarks land on the same unified ITA view.
    @bp.get('/ita/fleet')
    @bp.get('/intelligence/ita/fleet')
    def fleet_portal():
        return portal()

    @bp.get('/api/v1/ita/fleet')
    def fleet():
        if not fleet_enabled:
            return jsonify({'error': 'fleet_disabled'}), 404
        if not fleet_client or not fleet_client.configured:
            return jsonify({'error': 'fleet_not_configured'}), 503
        try:
            return jsonify(fleet_client.fleet(request.args.get('view', 'active')))
        except RuntimeError as exc:
            return jsonify({'error': str(exc)}), 502

    @bp.get('/api/v1/ita/fleet/<pulse_id>')
    def fleet_asset(pulse_id):
        if not fleet_enabled:
            return jsonify({'error': 'fleet_disabled'}), 404
        if not fleet_client or not fleet_client.configured:
            return jsonify({'error': 'fleet_not_configured'}), 503
        try:
            return jsonify(fleet_client.asset(pulse_id))
        except RuntimeError as exc:
            code = 404 if str(exc) == 'receiver_http_404' else 502
            return jsonify({'error': str(exc)}), code

    @bp.post('/api/v1/ita/fleet/<pulse_id>/asset-status')
    def set_fleet_asset_status(pulse_id):
        if not fleet_enabled:
            return jsonify({'error': 'fleet_disabled'}), 404
        if not fleet_client or not fleet_client.configured:
            return jsonify({'error': 'fleet_not_configured'}), 503
        body = request.get_json(silent=True) or {}
        try:
            return jsonify(fleet_client.set_asset_status(
                pulse_id,
                body.get('status'),
                body.get('reason', ''),
            ))
        except RuntimeError as exc:
            code = 404 if str(exc) == 'receiver_http_404' else 400 if str(exc) == 'receiver_http_400' else 502
            return jsonify({'error': str(exc)}), code

    @bp.delete('/api/v1/ita/fleet/<pulse_id>')
    def delete_fleet_asset(pulse_id):
        if not fleet_enabled:
            return jsonify({'error': 'fleet_disabled'}), 404
        if not fleet_client or not fleet_client.configured:
            return jsonify({'error': 'fleet_not_configured'}), 503
        try:
            return jsonify(fleet_client.delete_asset(pulse_id))
        except RuntimeError as exc:
            code = 404 if str(exc) == 'receiver_http_404' else 409 if str(exc) == 'receiver_http_409' else 502
            return jsonify({'error': str(exc)}), code

    @bp.get('/api/v1/ita/systems')
    def systems():
        return jsonify({'items': repo.systems(request.args.get('view', 'active'))})

    @bp.get('/api/v1/ita/portfolio')
    def portfolio():
        return jsonify(repo.portfolio(request.args.get('view', 'active')))

    @bp.get('/api/v1/ita/systems/<system_id>/current')
    def current(system_id):
        result = repo.current(system_id)
        return (jsonify(result), 200) if result else (jsonify({'error': 'system_not_found'}), 404)

    @bp.get('/api/v1/ita/systems/<system_id>/history')
    def history(system_id):
        return jsonify(repo.history(system_id, request.args.get('hours', 24)))

    @bp.get('/api/v1/ita/systems/<system_id>/events')
    def events(system_id):
        return jsonify(repo.events(system_id, request.args.get('limit', 100)))

    @bp.get('/api/v1/ita/systems/<system_id>/asset-status')
    def asset_status(system_id):
        return jsonify(repo.asset_status(system_id))

    @bp.post('/api/v1/ita/systems/<system_id>/asset-status')
    def set_asset_status(system_id):
        body = request.get_json(silent=True) or {}
        try:
            result = repo.set_asset_status(system_id, body.get('status'), body.get('reason', ''))
        except ValueError:
            return jsonify({'error': 'invalid_asset_status', 'allowed': ['active', 'hidden', 'decommissioned']}), 400
        return jsonify(result)

    @bp.delete('/api/v1/ita/systems/<system_id>')
    def delete_local_asset(system_id):
        try:
            result = repo.delete_asset(system_id)
        except ValueError:
            return jsonify({'error': 'invalid_system_id'}), 400
        if not result:
            return jsonify({'error': 'system_not_found'}), 404
        return jsonify(result)

    return bp
