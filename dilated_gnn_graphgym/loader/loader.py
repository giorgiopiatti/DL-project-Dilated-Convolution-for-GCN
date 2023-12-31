import torch_geometric.transforms as T
from torch_geometric.datasets import (
    PPI,
    Amazon,
    Coauthor,
    KarateClub,
    MNISTSuperpixels,
    Planetoid,
    QM7b,
    TUDataset,
)
from torch_geometric.graphgym.config import cfg
from dilated_gnn_graphgym.loader.bottleneck import create_bottleneck_dataloader

from dilated_gnn_graphgym.loader.ogb import create_loader_ogb
from dilated_gnn_graphgym.loader.tudataset import create_loader_tu

from dilated_gnn_graphgym.transform.transform_dilated_mp_graph import DilatedMPGraphTransform
from dilated_gnn_graphgym.transform.transform_dilated_mp_graph_edge_features import DilatedMPGraphEdgeFeaturesTransform
from dilated_gnn_graphgym.transform.transform_dilated_leafs_mp_graph_edge_features import DilatedLeafsMPGraphEdgeFeaturesTransform
from dilated_gnn_graphgym.transform.transform_dilated_leafs_mp_graph import DilatedLeafsMPGraphTransform
from dilated_gnn_graphgym.transform.transform_node_features import EmptyNodeFeatures 


def ___load_pyg(name, dataset_dir):
    """
    Load PyG dataset objects. (More PyG datasets will be supported)

    Args:
        name (string): dataset name
        dataset_dir (string): data directory

    Returns: PyG dataset object

    """
    dataset_dir = '{}/{}'.format(dataset_dir, name)
    if name in ['Cora', 'CiteSeer', 'PubMed']:
        dataset = Planetoid(dataset_dir, name)
    elif name[:3] == 'TU_':
        # TU_IMDB doesn't have node features
        if name[3:] == 'IMDB':
            name = 'IMDB-MULTI'
            dataset = TUDataset(dataset_dir, name, transform=T.Constant())
        else:
            dataset = TUDataset(dataset_dir, name[3:])
    elif name == 'Karate':
        dataset = KarateClub()
    elif 'Coauthor' in name:
        if 'CS' in name:
            dataset = Coauthor(dataset_dir, name='CS')
        else:
            dataset = Coauthor(dataset_dir, name='Physics')
    elif 'Amazon' in name:
        if 'Computers' in name:
            dataset = Amazon(dataset_dir, name='Computers')
        else:
            dataset = Amazon(dataset_dir, name='Photo')
    elif name == 'MNIST':
        dataset = MNISTSuperpixels(dataset_dir)
    elif name == 'PPI':
        dataset = PPI(dataset_dir)
    elif name == 'QM7b':
        dataset = QM7b(dataset_dir)
    else:
        raise ValueError('{} not support'.format(name))

    return dataset


cfg.gnn.use_edge_features = False
cfg.dataset.preprocesss_dataset = False

cfg.dataset.positional_encoding_path = False
cfg.dataset.use_sparse_adj = False
def create_loader():
    """
    Create data loader objects in array
    [train, val, test]
    """

    format = cfg.dataset.format
    name = cfg.dataset.name
    dataset_dir = cfg.dataset.dir

    # Transformer based on dataset and model
    if cfg.model.type == 'dilated_gnn':
        if cfg.gnn.use_edge_features :
            transform = DilatedMPGraphEdgeFeaturesTransform(cfg.gnn.layers_k1, cfg.gnn.layers_k2)
        else:
            transform = DilatedMPGraphTransform(cfg.gnn.layers_k1, cfg.gnn.layers_k2)
    elif cfg.model.type == 'dilapos_gnn':
        if cfg.gnn.use_edge_features :
            if cfg.dataset.use_sparse_adj:
                raise ValueError(f'cfg.dataset.use_sparse_adj is set to true, but this is incompatible with cfg.gnn.use_edge_features=True')
            transform = DilatedLeafsMPGraphEdgeFeaturesTransform(cfg.gnn.layers_k1, cfg.gnn.layers_k2)
        else:
            if cfg.dataset.use_sparse_adj and cfg.dataset.positional_encoding_path:
                raise ValueError(f'cfg.dataset.use_sparse_adj is set to true, but this is incompatible with cfg.dataset.positional_encoding_path=True')
            transform = DilatedLeafsMPGraphTransform(cfg.gnn.layers_k1, cfg.gnn.layers_k2, cfg.dataset.use_sparse_adj, cfg.dataset.positional_encoding_path)
    else:
        transform = EmptyNodeFeatures()

    pre_transform = None
    if cfg.dataset.preprocesss_dataset and cfg.model.type == 'dilated_gnn' and not cfg.gnn.use_edge_features:
        pre_transform = transform
        transform = None
        dataset_dir = f'{dataset_dir}/cache/k1={cfg.gnn.layers_k1}_k2={cfg.gnn.layers_k2}/'
    elif cfg.dataset.preprocesss_dataset and cfg.model.type == 'dilapos_gnn' and not cfg.gnn.use_edge_features:
        pre_transform = transform
        transform = None
        if cfg.dataset.positional_encoding_path:
            dataset_dir = f'{dataset_dir}/cache_dilapos_path_encoded/k1={cfg.gnn.layers_k1}_k2={cfg.gnn.layers_k2}/'
        else:
            dataset_dir = f'{dataset_dir}/cache_dilapos/k1={cfg.gnn.layers_k1}_k2={cfg.gnn.layers_k2}/'

    # Load from Pytorch Geometric dataset
    if format == 'TU':
        dataset = create_loader_tu(name, dataset_dir, transform, pre_transform)
    # Load from OGB formatted data
    elif format == 'OGB':
        dataset = create_loader_ogb(name, dataset_dir, transform)
    elif format == 'BOTTLENECK':
        dataset = create_bottleneck_dataloader(name, dataset_dir, transform, pre_transform)
    else:
        raise ValueError('Unknown data format: {}'.format(format))

    if cfg.gnn.use_edge_features and cfg.dataset.edge_dim == 0:
        raise ValueError('Edge feature are not present, but "cfg.gnn.use_edge_features" is True')

    return dataset




