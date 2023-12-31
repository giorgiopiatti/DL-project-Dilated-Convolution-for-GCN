import torch
import torch.nn as nn

from torch_geometric.graphgym.config import cfg
from torch_geometric.graphgym.register import register_stage
import torch_geometric.graphgym.register as register
from dilated_gnn_graphgym.layer.dilated_positional_gnn_layer import create_dilated_positional_gnn_layer
from torch_geometric.graphgym.models.layer import GeneralLayer, new_layer_config

def create_classic_gnn_layer(dim_in, dim_out, has_act=True, final=False):
    """
    Wrapper for a GNN layer

    Args:
        dim_in (int): Input dimension
        dim_out (int): Output dimension
        has_act (bool): Whether has activation function after the layer

    """
    layer_conf = new_layer_config(dim_in, dim_out, 1, has_act=has_act,
                                      has_bias=False, cfg=cfg)
    
    if  cfg.gnn.layer_type == 'edge_gatconv' or  cfg.gnn.layer_type == 'gatconv_paper':
        num_heads = cfg.gnn.att_heads_final if final else cfg.gnn.att_heads
        return GeneralLayer(
            cfg.gnn.layer_type,
            layer_config=layer_conf, num_heads=num_heads, attention_concat=not final)
    else:
        return GeneralLayer(
            cfg.gnn.layer_type,
            layer_config=layer_conf)


cfg.gnn.layers_k1 = 1
cfg.gnn.layers_k2 = 1
cfg.gnn.learn_alpha_residual_connection = True
cfg.gnn.dilated_path_join = 'concat'
class GNNDilatedPositionalStage(nn.Module):

    def __init__(self, dim_in, dim_out, num_layers) -> None:
        super().__init__()
        #Standard GNN
        self.cfg = cfg
        self.k1 = cfg.gnn.layers_k1
        self.classic_layers = nn.ModuleList()
        for i in range(self.k1):
            d_in = dim_in if i == 0 else dim_out
            has_act = True
            if i == self.k1 - 1: #last layer
                has_act = cfg.gnn.act_on_last_layer_mp
            layer = create_classic_gnn_layer(d_in, dim_out, has_act)
            self.classic_layers.append(layer)

        # Dilated GNN
        self.k2 = cfg.gnn.layers_k2

        if cfg.gnn.learn_alpha_residual_connection:
            self.alphas = nn.Parameter(torch.full((self.k2,), 0.0))
        self.dilated_layers = nn.ModuleList()

        for i in range(self.k2):
            has_act = True
            final = False
            if i == self.k2 - 1: #last layer
                has_act = cfg.gnn.act_on_last_layer_mp
                final = True
            layer = create_dilated_positional_gnn_layer(dim_out, dim_out, has_act,final)
            self.dilated_layers.append(layer)

        self.act = register.act_dict[cfg.gnn.act]()

    def forward(self, batch):
        #Classic layers
        save_intermediate = self.cfg.model.graph_pooling == 'concat_across_sum_of_layers' or self.cfg.model.graph_pooling == 'max_of_concat_layers'
        h = []

        for i in range(self.k1):
            batch = self.classic_layers[i](batch)
            if save_intermediate and i < self.k1 - 1:
                h.append(batch.x)

        x = batch.x

        if not self.cfg.gnn.act_on_last_layer_mp: #perform activation if not already done
            batch.x = self.act(batch.x)

        if save_intermediate: #case agnostic of above option
            h.append(batch.x)

        #Call GNN layers + weighted residual connections (check terminology)
        for step in range(self.k2):
            layer = self.dilated_layers[step]
            new_batch = layer(batch, step)
            if self.cfg.gnn.learn_alpha_residual_connection:
                alpha = torch.sigmoid(self.alphas[step])
                new_batch.x = alpha*new_batch.x + (torch.tensor(1.0) - alpha)*batch.x
            else:
                new_batch.x = new_batch.x + batch.x
            
            batch = new_batch

            if save_intermediate:
                h.append(batch.x)
        
        #Skip connection between 2 paths
        if self.cfg.gnn.dilated_path_join == 'concat':
            batch.x = torch.cat([batch.x, x], dim=1)
        elif self.cfg.gnn.dilated_path_join == 'add':
            batch.x = batch.x + x
        
        if save_intermediate:
            batch.x = torch.stack(h)
        return batch       